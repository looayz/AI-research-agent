import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db, AsyncSessionLocal
from app.models.research import Research, ResearchStatus, Source
from app.schemas.research import (
    ResearchCreateRequest,
    ResearchBasicResponse,
    ResearchDetailResponse,
    SourceSchema,
    ClaimSchema,
    ContradictionSchema,
    ReportSchema,
    ResearchEventSchema,
)
from app.services.orchestrator import ResearchOrchestrator

router = APIRouter(prefix="/research", tags=["Research"])


async def execute_background_research(research_id: str):
    async with AsyncSessionLocal() as session:
        orchestrator = ResearchOrchestrator(session)
        await orchestrator.run_pipeline(research_id)


@router.post("", response_model=ResearchBasicResponse, status_code=status.HTTP_201_CREATED)
async def create_research(
    payload: ResearchCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    research = Research(
        question=payload.question,
        depth=payload.depth,
        domain=payload.domain,
        status=ResearchStatus.CREATED
    )
    db.add(research)
    await db.commit()
    await db.refresh(research)

    background_tasks.add_task(execute_background_research, research.id)
    return research


@router.get("", response_model=list[ResearchDetailResponse])
async def list_researches(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Research)
        .options(
            selectinload(Research.plan),
            selectinload(Research.queries),
            selectinload(Research.sources),
            selectinload(Research.claims),
            selectinload(Research.contradictions),
            selectinload(Research.report)
        )
        .order_by(desc(Research.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{research_id}", response_model=ResearchDetailResponse)
async def get_research_detail(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Research)
        .where(Research.id == research_id)
        .options(
            selectinload(Research.plan),
            selectinload(Research.queries),
            selectinload(Research.sources),
            selectinload(Research.claims),
            selectinload(Research.contradictions),
            selectinload(Research.report)
        )
    )
    result = await db.execute(stmt)
    research = result.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@router.post("/{research_id}/rerun", response_model=ResearchBasicResponse)
async def rerun_research(
    research_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    old = await db.get(Research, research_id)
    if not old:
        raise HTTPException(status_code=404, detail="Research not found")

    new_research = Research(
        question=old.question,
        depth=old.depth,
        domain=old.domain,
        status=ResearchStatus.CREATED
    )
    db.add(new_research)
    await db.commit()
    await db.refresh(new_research)

    background_tasks.add_task(execute_background_research, new_research.id)
    return new_research


@router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    await db.delete(research)
    await db.commit()
    return None


@router.get("/{research_id}/events")
async def stream_research_events(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        sent_event_ids = set()
        while True:
            async with AsyncSessionLocal() as session:
                stmt = select(Research).where(Research.id == research_id).options(selectinload(Research.events))
                res = await session.execute(stmt)
                current_research = res.scalar_one_or_none()

                if current_research:
                    for ev in current_research.events:
                        if ev.id not in sent_event_ids:
                            sent_event_ids.add(ev.id)
                            payload = {
                                "id": ev.id,
                                "event_type": ev.event_type,
                                "agent": ev.agent,
                                "data": ev.data,
                                "status": current_research.status,
                                "created_at": ev.created_at.isoformat()
                            }
                            yield f"data: {json.dumps(payload)}\n\n"

                    if current_research.status in (ResearchStatus.COMPLETED, ResearchStatus.FAILED, ResearchStatus.CANCELLED):
                        break

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{research_id}/sources/{source_id}/exclude")
async def exclude_source(
    research_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Source).where(Source.id == source_id, Source.research_id == research_id)
    res = await db.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_excluded = True
    await db.commit()
    return {"message": "Source excluded successfully", "source_id": source_id}


@router.post("/{research_id}/cancel")
async def cancel_research(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if research.status not in (ResearchStatus.COMPLETED, ResearchStatus.FAILED):
        research.status = ResearchStatus.CANCELLED
        await db.commit()
    return {"message": "Research cancelled", "status": research.status}


@router.get("/{research_id}/sources", response_model=list[SourceSchema])
async def get_research_sources(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Research).where(Research.id == research_id).options(selectinload(Research.sources))
    res = await db.execute(stmt)
    research = res.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return [s for s in research.sources if not s.is_excluded]


@router.get("/{research_id}/claims", response_model=list[ClaimSchema])
async def get_research_claims(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Research).where(Research.id == research_id).options(selectinload(Research.claims))
    res = await db.execute(stmt)
    research = res.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research.claims


@router.get("/{research_id}/contradictions", response_model=list[ContradictionSchema])
async def get_research_contradictions(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Research).where(Research.id == research_id).options(selectinload(Research.contradictions))
    res = await db.execute(stmt)
    research = res.scalar_one_or_none()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research.contradictions


@router.get("/{research_id}/report", response_model=ReportSchema)
async def get_research_report(
    research_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Research).where(Research.id == research_id).options(selectinload(Research.report))
    res = await db.execute(stmt)
    research = res.scalar_one_or_none()
    if not research or not research.report:
        raise HTTPException(status_code=404, detail="Report not ready or research not found")
    return research.report
