from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    published_date: Optional[str] = None
    # Full text when the provider already returns it (Tavily raw content,
    # Wikipedia extracts, arXiv abstracts); the page is then not fetched.
    content: Optional[str] = None
    # Provider-side relevance in [0, 1] when available.
    score: Optional[float] = None
    # Hint for source classification, e.g. "preprint" or "encyclopedia".
    source_type: Optional[str] = None
    provider: str = ""


class SearchError(RuntimeError):
    """Raised when a search provider is misconfigured or its API fails."""


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        """Search the web. ``domain`` is the research profile (general/academic/technical/market)."""
