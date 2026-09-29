"""Real search providers: Tavily, SearXNG, DuckDuckGo, Wikipedia and arXiv."""

import asyncio
import html
import re
import time
import weakref
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.text import keywords
from app.providers.http import error_detail, request_with_retries
from app.providers.search.base import SearchError, SearchProvider, SearchResult

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


class _HTTPSearchProvider(SearchProvider):
    def __init__(self, timeout: float = settings.SEARCH_TIMEOUT_SECONDS, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.timeout = timeout
        self._transport = transport

    def _client(self, **kwargs) -> httpx.AsyncClient:
        headers = {"User-Agent": settings.FETCH_USER_AGENT, **kwargs.pop("headers", {})}
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport, headers=headers, **kwargs)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._client() as client:
            try:
                response = await request_with_retries(client, method, url, **kwargs)
            except httpx.HTTPError as exc:
                raise SearchError(f"{self.name}: request failed ({type(exc).__name__})") from exc
        if response.status_code >= 400:
            raise SearchError(f"{self.name}: HTTP {response.status_code} - {error_detail(response)}")
        return response


class TavilySearchProvider(_HTTPSearchProvider):
    """https://tavily.com - search API built for agents, returns page content."""

    name = "tavily"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        if not self.api_key:
            raise SearchError("tavily: missing API key (set TAVILY_API_KEY)")
        payload = {
            "query": query[:400],
            "max_results": max(1, min(max_results, 20)),
            "search_depth": "advanced" if domain in ("academic", "market") else "basic",
            "include_raw_content": True,
            "include_answer": False,
        }
        response = await self._request(
            "POST", "https://api.tavily.com/search", json=payload, headers={"Authorization": f"Bearer {self.api_key}"}
        )
        results = []
        for item in response.json().get("results", []):
            if not item.get("url"):
                continue
            raw = item.get("raw_content") or None
            results.append(
                SearchResult(
                    title=item.get("title") or item["url"],
                    url=item["url"],
                    snippet=item.get("content") or "",
                    content=raw if raw and len(raw) > 200 else None,
                    published_date=item.get("published_date"),
                    score=item.get("score"),
                    provider=self.name,
                )
            )
        return results


class SearxngSearchProvider(_HTTPSearchProvider):
    """Self-hosted SearXNG metasearch (JSON output must be enabled in settings.yml)."""

    name = "searxng"
    _CATEGORIES = {"academic": "science", "technical": "it", "market": "news"}

    def __init__(self, base_url: str, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        if not self.base_url:
            raise SearchError("searxng: SEARXNG_BASE_URL is not set")
        params = {"q": query, "format": "json", "safesearch": 1, "categories": self._CATEGORIES.get(domain, "general")}
        response = await self._request("GET", f"{self.base_url}/search", params=params)
        try:
            items = response.json().get("results", [])
        except ValueError as exc:
            raise SearchError("searxng: JSON output is disabled (add 'json' to search.formats)") from exc
        top = max((item.get("score") or 0 for item in items), default=0) or 1
        return [
            SearchResult(
                title=item.get("title") or item["url"],
                url=item["url"],
                snippet=item.get("content") or "",
                published_date=item.get("publishedDate"),
                score=round((item.get("score") or 0) / top, 3),
                provider=self.name,
            )
            for item in items[:max_results]
            if item.get("url")
        ]


class DuckDuckGoSearchProvider(_HTTPSearchProvider):
    """Keyless best-effort search through DuckDuckGo's HTML endpoint (may be rate limited)."""

    name = "duckduckgo"

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        response = await self._request("POST", "https://html.duckduckgo.com/html/", data={"q": query, "kl": "wt-wt"})
        if response.status_code == 202 or "anomaly" in response.text[:5000].lower():
            raise SearchError("duckduckgo: rate limited (bot challenge), use another provider")
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for block in soup.select("div.result"):
            if "result--ad" in (block.get("class") or []):
                continue
            link = block.select_one("a.result__a")
            if link is None or not link.get("href"):
                continue
            href = link["href"]
            if "uddg=" in href:
                href = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith(("http://", "https://")):
                continue
            snippet = block.select_one(".result__snippet")
            results.append(
                SearchResult(
                    title=link.get_text(" ", strip=True) or href,
                    url=href,
                    snippet=snippet.get_text(" ", strip=True) if snippet else "",
                    provider=self.name,
                )
            )
            if len(results) >= max_results:
                break
        return results


class WikipediaSearchProvider(_HTTPSearchProvider):
    """Keyless and reliable: Wikipedia search + plain-text article intros."""

    name = "wikipedia"

    def __init__(self, lang: str = "en", **kwargs):
        super().__init__(**kwargs)
        self.lang = lang

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": query[:300],
            "gsrlimit": max(1, min(max_results, 10)),
            "prop": "extracts|info|revisions",
            "exintro": 1,
            "explaintext": 1,
            "exlimit": "max",
            "inprop": "url",
            "rvprop": "timestamp",
        }
        response = await self._request("GET", f"https://{self.lang}.wikipedia.org/w/api.php", params=params)
        pages = response.json().get("query", {}).get("pages", [])
        pages.sort(key=lambda page: page.get("index", 0))
        results = []
        for rank, page in enumerate(pages):
            extract = (page.get("extract") or "").strip()
            if not extract:
                continue
            url = page.get("fullurl") or f"https://{self.lang}.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}"
            revisions = page.get("revisions") or [{}]
            results.append(
                SearchResult(
                    title=f"{page['title']} - Wikipedia",
                    url=url,
                    snippet=extract[:300],
                    content=extract,
                    published_date=(revisions[0].get("timestamp") or "")[:10] or None,
                    score=round(1 - rank / max(len(pages), 1), 3),
                    source_type="encyclopedia",
                    provider=self.name,
                )
            )
        return results


class ArxivSearchProvider(_HTTPSearchProvider):
    """arXiv preprints (titles + abstracts). Best combined with another provider."""

    name = "arxiv"
    _ATOM = "{http://www.w3.org/2005/Atom}"
    # One lock per event loop: asyncio primitives must not cross loops.
    _locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()
    _last_call = 0.0

    @classmethod
    def _lock(cls) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = cls._locks.get(loop)
        if lock is None:
            lock = cls._locks[loop] = asyncio.Lock()
        return lock

    async def _throttled_get(self, params: dict) -> httpx.Response:
        # arXiv asks API clients to wait 3 seconds between requests.
        async with self._lock():
            wait = 3.0 - (time.monotonic() - ArxivSearchProvider._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await self._request("GET", "https://export.arxiv.org/api/query", params=params)
            finally:
                ArxivSearchProvider._last_call = time.monotonic()

    def _parse(self, xml_text: str) -> list[SearchResult]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise SearchError("arxiv: invalid Atom response") from exc
        results = []
        entries = root.findall(f"{self._ATOM}entry")
        for rank, entry in enumerate(entries):
            url = (entry.findtext(f"{self._ATOM}id") or "").strip().replace("http://", "https://", 1)
            title = re.sub(r"\s+", " ", entry.findtext(f"{self._ATOM}title") or "").strip()
            summary = re.sub(r"\s+", " ", entry.findtext(f"{self._ATOM}summary") or "").strip()
            if not url or not title:
                continue
            authors = [a.findtext(f"{self._ATOM}name") or "" for a in entry.findall(f"{self._ATOM}author")]
            byline = ", ".join(a for a in authors[:4] if a) + (" et al." if len(authors) > 4 else "")
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=summary[:300],
                    content=f"{title}\nAuthors: {byline}\n\n{summary}" if byline else f"{title}\n\n{summary}",
                    published_date=(entry.findtext(f"{self._ATOM}published") or "")[:10] or None,
                    score=round(1 - rank / max(len(entries), 1), 3),
                    source_type="preprint",
                    provider=self.name,
                )
            )
        return results

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        words = [re.sub(r"[^\w-]", "", w) for w in keywords(query, limit=6)]
        words = [w for w in words if w]
        if not words:
            return []
        # All keywords first, then a looser query if that is too strict.
        for subset in (words, words[:3]):
            params = {
                "search_query": " AND ".join(f"all:{w}" for w in subset),
                "start": 0,
                "max_results": max(1, min(max_results, 10)),
                "sortBy": "relevance",
            }
            results = self._parse((await self._throttled_get(params)).text)
            if results or len(subset) <= 3:
                return results
        return []
