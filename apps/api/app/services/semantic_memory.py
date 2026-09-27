from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.research import Source
from app.services.embedding import EmbeddingService


class SemanticMemoryService:
    @staticmethod
    async def find_relevant_past_sources(
        db: AsyncSession,
        query: str,
        threshold: float = 0.65,
        limit: int = 5
    ) -> List[Tuple[Source, float]]:
        """
        Scan past sources across all previous investigations and retrieve semantically
        similar items using cosine similarity over precomputed embeddings.
        """
        query_vector = EmbeddingService.compute_embedding(query)

        stmt = select(Source).where(Source.is_excluded == False)
        result = await db.execute(stmt)
        sources = result.scalars().all()

        scored_sources = []
        for src in sources:
            if src.embedding and len(src.embedding) > 0:
                sim = EmbeddingService.cosine_similarity(query_vector, src.embedding)
                if sim >= threshold:
                    scored_sources.append((src, round(sim, 3)))

        # Sort by similarity descending
        scored_sources.sort(key=lambda x: x[1], reverse=True)
        return scored_sources[:limit]
