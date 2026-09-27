from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Perform search query and return list of results."""
        pass
