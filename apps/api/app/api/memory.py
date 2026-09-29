from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.research import Research
from app.schemas.research import SourceSchema
from app.services.semantic_memory import SemanticMemoryService

router = APIRouter(prefix="/memory", tags=["Semantic Memory"])


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    threshold: float = Field(0.3, ge=0.0, le=1.0)
    limit: int = Field(10, ge=1, le=50)


class MemorySearchResponse(BaseModel):
    source: SourceSchema
    similarity_score: float
    research_question: Optional[str] = None


@router.post("/search", response_model=list[MemorySearchResponse])
async def search_memory(payload: MemorySearchRequest, db: AsyncSession = Depends(get_db)):
    """Similarity search over every source collected by past investigations."""
    matches = await SemanticMemoryService.find_relevant_past_sources(
        db=db, query=payload.query, threshold=payload.threshold, limit=payload.limit
    )
    research_ids = {src.research_id for src, _ in matches}
    questions = (
        dict((await db.execute(select(Research.id, Research.question).where(Research.id.in_(research_ids)))).all())
        if research_ids
        else {}
    )
    return [
        MemorySearchResponse(
            source=SourceSchema.model_validate(src),
            similarity_score=score,
            research_question=questions.get(src.research_id),
        )
        for src, score in matches
    ]
