import asyncio
import hashlib
import logging

from app.core.cache import get_cache
from app.core.config import settings
from app.core.text import normalize_url
from app.providers.search.base import SearchError, SearchProvider, SearchResult
from app.providers.search.mock import MockSearchProvider
from app.providers.search.web import (
    ArxivSearchProvider,
    DuckDuckGoSearchProvider,
    SearxngSearchProvider,
    TavilySearchProvider,
    WikipediaSearchProvider,
)

logger = logging.getLogger(__name__)

SEARCH_PROVIDERS = ("mock", "tavily", "searxng", "duckduckgo", "wikipedia", "arxiv")


class CompositeSearchProvider(SearchProvider):
    """Queries several providers concurrently and interleaves their results."""

    def __init__(self, providers: list[SearchProvider]):
        self.providers = providers
        self.name = "+".join(p.name for p in providers)

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        outcomes = await asyncio.gather(
            *(p.search(query, max_results=max_results, domain=domain) for p in self.providers), return_exceptions=True
        )
        lists: list[list[SearchResult]] = []
        errors: list[str] = []
        for provider, outcome in zip(self.providers, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning("Search provider %s failed: %s", provider.name, outcome)
                errors.append(str(outcome))
            else:
                lists.append(outcome)
        if not lists:
            raise SearchError("; ".join(errors) or "all search providers failed")

        merged: list[SearchResult] = []
        seen: set[str] = set()
        for rank in range(max((len(results) for results in lists), default=0)):
            for results in lists:
                if rank < len(results):
                    key = normalize_url(results[rank].url)
                    if key not in seen:
                        seen.add(key)
                        merged.append(results[rank])
        return merged[:max_results]


class CachedSearchProvider(SearchProvider):
    def __init__(self, inner: SearchProvider, ttl: int):
        self.inner = inner
        self.name = inner.name
        self.ttl = ttl

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        key = "search:" + hashlib.sha1(f"{self.name}|{domain}|{max_results}|{query}".encode()).hexdigest()
        cache = get_cache()
        cached = await cache.get_json(key)
        if cached is not None:
            return [SearchResult(**item) for item in cached]
        results = await self.inner.search(query, max_results=max_results, domain=domain)
        await cache.set_json(key, [r.model_dump() for r in results], self.ttl)
        return results


def _build(name: str) -> SearchProvider:
    if name == "mock":
        return MockSearchProvider()
    if name == "tavily":
        return TavilySearchProvider(settings.TAVILY_API_KEY)
    if name == "searxng":
        return SearxngSearchProvider(settings.SEARXNG_BASE_URL)
    if name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    if name == "wikipedia":
        return WikipediaSearchProvider(lang=settings.WIKIPEDIA_LANG)
    if name == "arxiv":
        return ArxivSearchProvider()
    raise SearchError(f"Unknown SEARCH_PROVIDER '{name}' (expected one of: {', '.join(SEARCH_PROVIDERS)})")


def configured_search_names() -> list[str]:
    spec = "mock" if settings.MOCK_MODE else settings.SEARCH_PROVIDER
    return [n.strip().lower() for n in spec.split(",") if n.strip()] or ["mock"]


def get_search_provider() -> SearchProvider:
    providers = [_build(name) for name in configured_search_names()]
    provider = providers[0] if len(providers) == 1 else CompositeSearchProvider(providers)
    if provider.name == "mock":
        return provider
    return CachedSearchProvider(provider, settings.CACHE_TTL_SECONDS)
