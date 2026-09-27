from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.services.semantic_memory import SemanticMemoryService
from app.schemas.research import SourceSchema

router = APIRouter(prefix="/memory", tags=["Semantic Memory"])


class MemorySearchRequest(BaseModel):
    query: str
    threshold: float = 0.5
    limit: int = 5


class MemorySearchResponse(BaseModel):
    source: SourceSchema
    similarity_score: float


@router.post("/search", response_model=List[MemorySearchResponse])
async def search_memory(
    payload: MemorySearchRequest,
    db: AsyncSession = Depends(get_db)
):
    matches = await SemanticMemoryService.find_relevant_past_sources(
        db=db,
        query=payload.query,
        threshold=payload.threshold,
        limit=payload.limit
    )
    return [
        MemorySearchResponse(
            source=SourceSchema.model_validate(src),
            similarity_score=sim
        )
        for src, sim in matches
    ]
