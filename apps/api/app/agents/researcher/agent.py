from typing import List, Dict, Any
from datetime import datetime, timezone
from app.providers.search.base import SearchProvider
from app.services.extractor import ContentExtractor
from app.services.embedding import EmbeddingService
from pydantic import BaseModel, Field


class CollectedSource(BaseModel):
    url: str
    title: str
    domain: str
    published_at: str | None = None
    retrieved_at: datetime
    content: str
    source_type: str = "web_article"
    relevance_score: float = 0.85
    evaluation_factors: Dict[str, Any] = {}
    evaluation_notes: List[str] = []
    embedding: List[float] = Field(default_factory=list)


class ResearcherAgent:
    def __init__(self, search_provider: SearchProvider):
        self.search = search_provider

    def _determine_source_type_and_score(self, domain: str, research_domain: str) -> tuple[str, float, list[str]]:
        domain_lower = domain.lower()
        notes = []

        if research_domain == "academic":
            if any(k in domain_lower for k in ("arxiv.org", "ieee.org", "sciencedirect.com", "nature.com", "springer.com", "acm.org")):
                notes.append("Scholarly peer-reviewed publisher")
                return "peer_reviewed_paper", 0.98, notes
            if ".edu" in domain_lower:
                notes.append("Academic institutional research")
                return "academic_publication", 0.92, notes

        elif research_domain == "technical":
            if any(k in domain_lower for k in ("docs.", "github.com", "developer.", "rfc-editor.org", "stackoverflow.com")):
                notes.append("Primary technical documentation")
                return "technical_documentation", 0.96, notes

        elif research_domain == "market":
            if any(k in domain_lower for k in ("statista.com", "bloomberg.com", "gartner.com", "reuters.com", "sec.gov")):
                notes.append("Market intelligence and regulatory filing")
                return "market_report", 0.94, notes

        if "docs." in domain_lower:
            notes.append("Authoritative documentation")
            return "documentation", 0.90, notes

        notes.append("Relevant web resource analyzed")
        return "web_article", 0.82, notes

    async def execute_searches(self, queries: List[str], research_domain: str = "general", max_per_query: int = 3) -> List[CollectedSource]:
        collected_sources: List[CollectedSource] = []
        seen_urls = set()

        for query in queries:
            targeted_query = query
            if research_domain == "academic" and not any(k in query.lower() for k in ("study", "paper", "arxiv")):
                targeted_query = f"{query} research study"
            elif research_domain == "technical" and not any(k in query.lower() for k in ("docs", "spec", "architecture")):
                targeted_query = f"{query} documentation specification"
            elif research_domain == "market" and not any(k in query.lower() for k in ("market", "industry", "report")):
                targeted_query = f"{query} industry market report"

            search_results = await self.search.search(query=targeted_query, max_results=max_per_query)
            for res in search_results:
                if res.url in seen_urls:
                    continue
                seen_urls.add(res.url)

                extracted = await ContentExtractor.extract_from_url(res.url)
                source_type, score, notes = self._determine_source_type_and_score(extracted.domain, research_domain)
                
                # Compute semantic vector embedding for long-term memory
                text_to_embed = f"{extracted.title} {extracted.content[:1000]}"
                vector = EmbeddingService.compute_embedding(text_to_embed)

                collected_sources.append(
                    CollectedSource(
                        url=res.url,
                        title=extracted.title or res.title,
                        domain=extracted.domain,
                        published_at=res.published_date,
                        retrieved_at=datetime.now(timezone.utc),
                        content=extracted.content or res.snippet,
                        source_type=source_type,
                        relevance_score=score,
                        evaluation_factors={"domain_reputation": score, "domain_alignment": 0.9},
                        evaluation_notes=notes,
                        embedding=vector
                    )
                )

        return collected_sources
