import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.cache import get_cache
from app.core.config import settings
from app.core.text import clip, domain_of, normalize_url
from app.providers.search.base import SearchError, SearchProvider, SearchResult
from app.services.embedding import EmbeddingService
from app.services.extractor import extract_document
from app.services.fetcher import FetchError, SafeFetcher
from app.services.semantic_memory import embedding_text

logger = logging.getLogger(__name__)

MIN_CONTENT_CHARS = 200
MIN_SNIPPET_CHARS = 40

# (domain markers, source type, authority)
_AUTHORITY_RULES: list[tuple[tuple[str, ...], str, float]] = [
    (
        (
            "nature.com",
            "science.org",
            "sciencedirect.com",
            "springer.com",
            "wiley.com",
            "ieee.org",
            "acm.org",
            "ncbi.nlm.nih.gov",
            "pubmed",
            "jstor.org",
            "plos.org",
            "thelancet.com",
            "nejm.org",
            "bmj.com",
            "cell.com",
            "pnas.org",
            "tandfonline.com",
            "sagepub.com",
            "frontiersin.org",
            "mdpi.com",
            "cochranelibrary.com",
        ),
        "peer_reviewed_paper",
        0.95,
    ),
    (("arxiv.org", "biorxiv.org", "medrxiv.org", "ssrn.com", "hal.science", "researchgate.net"), "preprint", 0.85),
    (
        (".gov", ".gouv.fr", "europa.eu", "who.int", "oecd.org", "worldbank.org", "imf.org", "un.org", "insee.fr"),
        "official",
        0.92,
    ),
    ((".edu", ".ac.uk", "univ-", "university"), "academic_publication", 0.88),
    (("rfc-editor.org", "ietf.org", "w3.org", "whatwg.org", "iso.org"), "specification", 0.93),
    (
        ("docs.", "developer.", "readthedocs.io", "python.org", "mozilla.org", "learn.microsoft.com"),
        "technical_documentation",
        0.9,
    ),
    (("github.com", "gitlab.com", "bitbucket.org"), "repository", 0.8),
    (("wikipedia.org",), "encyclopedia", 0.8),
    (
        ("statista.com", "gartner.com", "mckinsey.com", "sec.gov", "idc.com", "forrester.com", "bcg.com", "deloitte.com"),
        "market_report",
        0.88,
    ),
    (
        (
            "reuters.com",
            "apnews.com",
            "bbc.",
            "ft.com",
            "bloomberg.com",
            "economist.com",
            "nytimes.com",
            "lemonde.fr",
            "wsj.com",
            "theguardian.com",
            "lesechos.fr",
            "afp.com",
        ),
        "news",
        0.85,
    ),
    (("stackoverflow.com", "stackexchange.com"), "forum", 0.7),
    (("medium.com", "substack.com", "blogspot.", "wordpress.com", "dev.to", "hashnode"), "blog", 0.6),
    (("reddit.com", "quora.com", "facebook.com", "x.com", "twitter.com", "tiktok.com"), "social", 0.45),
]
_PROFILE_AFFINITY = {
    "academic": {"peer_reviewed_paper", "preprint", "academic_publication", "official"},
    "technical": {"technical_documentation", "specification", "repository", "forum"},
    "market": {"market_report", "news", "official", "analyst_report"},
}
_TYPE_LABELS = {
    "peer_reviewed_paper": "Peer-reviewed publisher",
    "preprint": "Preprint server (not peer reviewed)",
    "official": "Official / institutional source",
    "academic_publication": "Academic institution",
    "specification": "Standards body / specification",
    "technical_documentation": "Primary technical documentation",
    "repository": "Source code repository",
    "encyclopedia": "Encyclopedia",
    "market_report": "Market intelligence / filings",
    "news": "Established news outlet",
    "forum": "Q&A forum",
    "blog": "Blog / personal publication",
    "social": "Social media / community content",
}
_YEAR_RE = re.compile(r"(19|20)\d{2}")


class CollectedSource(BaseModel):
    url: str
    title: str
    domain: str
    published_at: Optional[str] = None
    retrieved_at: datetime
    content: str
    source_type: str = "web_article"
    relevance_score: float = 0.5
    evaluation_factors: dict[str, Any] = Field(default_factory=dict)
    evaluation_notes: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    origin: str = "search"
    origin_query: Optional[str] = None
    fetch_status: str = "ok"


@dataclass
class CollectionResult:
    sources: list[CollectedSource] = field(default_factory=list)
    results_per_query: dict[str, int] = field(default_factory=dict)
    search_calls: int = 0
    fetch_calls: int = 0
    failed_fetches: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class _Candidate:
    result: SearchResult
    query: str
    rank: int
    total: int


def classify_domain(domain: str, research_domain: str, hint: Optional[str] = None) -> tuple[str, float]:
    domain = domain.lower()
    source_type, authority = "web_article", 0.65
    for markers, kind, score in _AUTHORITY_RULES:
        if any(marker in domain for marker in markers):
            source_type, authority = kind, score
            break
    if hint and source_type == "web_article":
        source_type = hint
    if source_type in _PROFILE_AFFINITY.get(research_domain, set()):
        authority = min(1.0, authority + 0.05)
    return source_type, round(authority, 3)


def _freshness(published: Optional[str]) -> Optional[float]:
    if not published:
        return None
    match = _YEAR_RE.search(published)
    if not match:
        return None
    age = datetime.now(UTC).year - int(match.group(0))
    if age <= 1:
        return 1.0
    if age <= 3:
        return 0.8
    if age <= 6:
        return 0.6
    return 0.4


def score_source(
    *,
    domain: str,
    research_domain: str,
    question_vector: list[float],
    content: str,
    title: str,
    published: Optional[str],
    rank: int,
    total: int,
    provider_score: Optional[float],
    type_hint: Optional[str],
    snippet_only: bool,
) -> tuple[str, float, dict[str, Any], list[str], list[float]]:
    source_type, authority = classify_domain(domain, research_domain, type_hint)
    vector = EmbeddingService.compute_embedding(embedding_text(title, content))
    query_match = min(1.0, max(0.0, EmbeddingService.cosine_similarity(question_vector, vector)) / 0.45)
    search_rank = provider_score if provider_score is not None else 1.0 - rank / max(total, 1)
    search_rank = max(0.0, min(1.0, float(search_rank)))
    depth = 0.2 if snippet_only else min(1.0, len(content) / 3000)
    fresh = _freshness(published)

    relevance = (
        0.35 * authority + 0.25 * query_match + 0.20 * search_rank + 0.10 * depth + 0.10 * (fresh if fresh is not None else 0.6)
    )
    factors = {
        "authority": round(authority, 3),
        "query_match": round(query_match, 3),
        "search_rank": round(search_rank, 3),
        "content_depth": round(depth, 3),
        "freshness": round(fresh, 3) if fresh is not None else None,
    }
    notes = [_TYPE_LABELS.get(source_type, "General web resource")]
    if published:
        notes.append(f"Published {published[:10]}")
    return source_type, round(relevance, 3), factors, notes, vector


class ResearcherAgent:
    def __init__(self, search_provider: SearchProvider, fetcher_factory: Callable[[], SafeFetcher] = SafeFetcher):
        self.search = search_provider
        self.fetcher_factory = fetcher_factory

    async def _run_searches(self, queries: list[str], max_per_query: int, domain: str):
        semaphore = asyncio.Semaphore(3)

        async def one(query: str):
            async with semaphore:
                try:
                    return query, await self.search.search(query, max_results=max_per_query, domain=domain)
                except SearchError as exc:
                    return query, exc

        return await asyncio.gather(*(one(q) for q in queries))

    async def _fetch_page(self, fetcher: SafeFetcher, url: str) -> dict:
        cache = get_cache()
        key = "page:" + hashlib.sha1(url.encode("utf-8")).hexdigest()
        cached = await cache.get_json(key)
        if cached is not None:
            return cached
        page = await fetcher.fetch(url)
        doc = extract_document(page.text, page.final_url, page.content_type)
        data = {"title": doc.title, "content": doc.content, "published": doc.published_date}
        await cache.set_json(key, data, settings.CACHE_TTL_SECONDS)
        return data

    async def collect(
        self,
        queries: list[str],
        *,
        question: str,
        research_domain: str = "general",
        max_per_query: int = 4,
        max_new_sources: int = 12,
        known_urls: Optional[set[str]] = None,
        origin: str = "search",
    ) -> CollectionResult:
        outcome = CollectionResult()
        seen = {normalize_url(u) for u in (known_urls or set())}

        candidates: list[_Candidate] = []
        for query, results in await self._run_searches(queries, max_per_query, research_domain):
            outcome.search_calls += 1
            if isinstance(results, Exception):
                outcome.errors.append(str(results))
                outcome.results_per_query[query] = 0
                continue
            outcome.results_per_query[query] = len(results)
            for rank, result in enumerate(results):
                key = normalize_url(result.url)
                if key in seen or not result.url.startswith(("http://", "https://")):
                    continue
                seen.add(key)
                candidates.append(_Candidate(result, query, rank, len(results)))

        # Interleave by rank so every query contributes its best results first.
        candidates.sort(key=lambda c: c.rank)
        candidates = candidates[:max_new_sources]
        if not candidates:
            return outcome

        question_vector = EmbeddingService.compute_embedding(question)
        semaphore = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_FETCHES))

        async def materialize(fetcher: SafeFetcher, cand: _Candidate) -> Optional[CollectedSource]:
            result = cand.result
            title, published = result.title, result.published_date
            content, fetch_status, fetch_note = result.content or "", "provided", None
            if len(content) < MIN_CONTENT_CHARS:
                async with semaphore:
                    outcome.fetch_calls += 1
                    try:
                        page = await self._fetch_page(fetcher, result.url)
                        content, fetch_status = page["content"], "ok"
                        title = result.title or page["title"]
                        published = published or page["published"]
                    except FetchError as exc:
                        outcome.failed_fetches += 1
                        fetch_note = str(exc)
                        content = ""
            if len(content) < MIN_CONTENT_CHARS:
                snippet = (result.snippet or "").strip()
                if len(snippet) < MIN_SNIPPET_CHARS and len(content) < MIN_SNIPPET_CHARS:
                    return None
                content, fetch_status = max(content, snippet, key=len), "snippet"

            domain = domain_of(result.url)
            source_type, relevance, factors, notes, vector = score_source(
                domain=domain,
                research_domain=research_domain,
                question_vector=question_vector,
                content=content,
                title=title,
                published=published,
                rank=cand.rank,
                total=cand.total,
                provider_score=result.score,
                type_hint=result.source_type,
                snippet_only=fetch_status == "snippet",
            )
            factors["provider"] = result.provider or self.search.name
            if fetch_status == "snippet":
                notes.append(f"Only the search snippet is available ({clip(fetch_note or 'page not fetched', 80)})")
            elif fetch_status == "provided":
                notes.append("Full text supplied by the search provider")
            return CollectedSource(
                url=result.url,
                title=clip(title or domain, 300),
                domain=domain,
                published_at=clip(published, 100) or None,
                retrieved_at=datetime.now(UTC),
                content=content,
                source_type=source_type,
                relevance_score=relevance,
                evaluation_factors=factors,
                evaluation_notes=notes,
                embedding=vector,
                origin=origin,
                origin_query=cand.query,
                fetch_status=fetch_status,
            )

        async with self.fetcher_factory() as fetcher:
            materialized = await asyncio.gather(*(materialize(fetcher, c) for c in candidates))
        outcome.sources = [s for s in materialized if s is not None]
        return outcome
