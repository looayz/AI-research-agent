from typing import List
from app.providers.search.base import SearchProvider, SearchResult


class MockSearchProvider(SearchProvider):
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        query_lower = query.lower()
        if "python" in query_lower:
            return [
                SearchResult(
                    title="Python Official Documentation - Getting Started & Best Practices",
                    url="https://docs.python.org/3/tutorial/index.html",
                    snippet="The Python Tutorial introduces the reader informally to the basic concepts and features of the Python language and system. Project-driven exploration is recommended.",
                    published_date="2025-01-15"
                ),
                SearchResult(
                    title="Modern Approaches in CS Education: Project-Based Python Learning",
                    url="https://realpython.com/learning-paths/python-foundations/",
                    snippet="Studies indicate hands-on project creation significantly outpaces syntax memorization for long-term retention.",
                    published_date="2024-11-20"
                ),
                SearchResult(
                    title="AI-Assisted Coding in Pedagogy: Benefits and Pitfalls (2024 Study)",
                    url="https://arxiv.org/abs/2306.01234",
                    snippet="Students leveraging AI code explanation tools resolved syntax confusion 30% faster, though reliance on code generation impaired foundational algorithm skills.",
                    published_date="2024-06-10"
                )
            ][:max_results]

        # Generic mock results
        return [
            SearchResult(
                title=f"Investigation into {query} - Reference Document",
                url=f"https://example.org/research/{abs(hash(query)) % 1000}",
                snippet=f"Detailed analytical findings and observations regarding {query}.",
                published_date="2025-02-01"
            ),
            SearchResult(
                title=f"Comparative overview of {query}",
                url=f"https://research-portal.org/studies/{abs(hash(query)) % 500}",
                snippet=f"Empirical data, methodology evaluation and evidence cross-referencing on {query}.",
                published_date="2024-10-12"
            )
        ][:max_results]
