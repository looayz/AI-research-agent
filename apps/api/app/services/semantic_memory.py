from collections.abc import Iterable
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import normalize_url
from app.models.research import Source
from app.services.embedding import EMBEDDING_DIM, EmbeddingService


def embedding_text(title: str, content: str) -> str:
    return f"{title} {content[:1500]}"


class SemanticMemoryService:
    @staticmethod
    async def _refresh_stale_embeddings(db: AsyncSession, source_ids: list[str]) -> dict[str, list[float]]:
        """Recompute embeddings produced by an older algorithm/dimension."""
        refreshed: dict[str, list[float]] = {}
        for start in range(0, len(source_ids), 200):
            chunk = source_ids[start : start + 200]
            rows = (await db.execute(select(Source.id, Source.title, Source.content).where(Source.id.in_(chunk)))).all()
            for row in rows:
                refreshed[row.id] = EmbeddingService.compute_embedding(embedding_text(row.title, row.content))
        if refreshed:
            # ORM bulk UPDATE by primary key
            await db.execute(update(Source), [{"id": sid, "embedding": emb} for sid, emb in refreshed.items()])
            await db.commit()
        return refreshed

    @staticmethod
    async def find_relevant_past_sources(
        db: AsyncSession,
        query: str,
        threshold: float = 0.35,
        limit: int = 5,
        exclude_research_id: Optional[str] = None,
        exclude_urls: Iterable[str] = (),
    ) -> list[tuple[Source, float]]:
        """Rank past sources (all investigations) by similarity to ``query``.

        Results are de-duplicated by URL: the same page collected by several
        investigations is returned once, with its best score.
        """
        query_vector = EmbeddingService.compute_embedding(query)
        if not any(query_vector):
            return []

        stmt = select(Source.id, Source.url, Source.embedding).where(Source.is_excluded.is_(False))
        if exclude_research_id:
            stmt = stmt.where(Source.research_id != exclude_research_id)
        rows = (await db.execute(stmt)).all()

        stale = [row.id for row in rows if len(row.embedding or []) != EMBEDDING_DIM]
        refreshed = await SemanticMemoryService._refresh_stale_embeddings(db, stale) if stale else {}

        skip = {normalize_url(u) for u in exclude_urls}
        best: dict[str, tuple[str, float]] = {}
        for row in rows:
            key = normalize_url(row.url)
            if key in skip:
                continue
            vector = refreshed.get(row.id, row.embedding)
            score = EmbeddingService.cosine_similarity(query_vector, vector)
            if score >= threshold and (key not in best or score > best[key][1]):
                best[key] = (row.id, score)

        ranked = sorted(best.values(), key=lambda item: item[1], reverse=True)[:limit]
        if not ranked:
            return []
        sources = {
            src.id: src for src in (await db.execute(select(Source).where(Source.id.in_([sid for sid, _ in ranked])))).scalars()
        }
        return [(sources[sid], round(score, 3)) for sid, score in ranked if sid in sources]
