import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_db
from app.core.text import strip_accents
from app.models.research import (
    TERMINAL_STATUSES,
    Claim,
    Contradiction,
    Report,
    Research,
    ResearchEvent,
    ResearchStatus,
    SearchQuery,
    Source,
)
from app.schemas.research import (
    ClaimSchema,
    ContradictionSchema,
    ReportSchema,
    ResearchBasicResponse,
    ResearchCreateRequest,
    ResearchDetailResponse,
    ResearchEventSchema,
    ResearchListResponse,
    ResearchSummaryResponse,
    SourceDetailSchema,
    SourceSchema,
)
from app.services.event_bus import event_bus
from app.services.orchestrator import ResearchOrchestrator
from app.services.tasks import task_manager

router = APIRouter(prefix="/research", tags=["Research"])

KEEPALIVE_SECONDS = 15.0
POLL_SECONDS = 1.0


def start_pipeline(research_id: str, mode: str = "full") -> None:
    task_manager.start(research_id, lambda: ResearchOrchestrator().run(research_id, mode=mode))


async def _get_research(db: AsyncSession, research_id: str) -> Research:
    research = await db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


async def _get_detail(db: AsyncSession, research_id: str) -> Research:
    stmt = (
        select(Research)
        .where(Research.id == research_id)
        .options(
            selectinload(Research.plan),
            selectinload(Research.queries),
            selectinload(Research.sources),
            selectinload(Research.claims),
            selectinload(Research.contradictions),
            selectinload(Research.events),
            selectinload(Research.report),
        )
    )
    research = (await db.execute(stmt)).scalar_one_or_none()
    if research is None:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@router.post("", response_model=ResearchBasicResponse, status_code=status.HTTP_201_CREATED)
async def create_research(payload: ResearchCreateRequest, db: AsyncSession = Depends(get_db)):
    research = Research(question=payload.question, depth=payload.depth, domain=payload.domain, status=ResearchStatus.CREATED)
    db.add(research)
    await db.commit()
    start_pipeline(research.id)
    return research


def _count(model, *conditions):
    return select(func.count(model.id)).where(model.research_id == Research.id, *conditions).correlate(Research).scalar_subquery()


@router.get("", response_model=ResearchListResponse)
async def list_researches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, max_length=200, description="Filter on the question text"),
    status_filter: Optional[ResearchStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q and q.strip():
        filters.append(Research.question.icontains(q.strip(), autoescape=True))
    if status_filter is not None:
        filters.append(Research.status == status_filter)

    report_title = select(Report.title).where(Report.research_id == Research.id).correlate(Research).scalar_subquery()
    summary = select(Report.executive_summary).where(Report.research_id == Research.id).correlate(Research).scalar_subquery()
    stmt = (
        select(
            Research,
            report_title.label("report_title"),
            summary.label("executive_summary"),
            _count(Source).label("source_count"),
            _count(Claim).label("claim_count"),
            _count(Contradiction).label("contradiction_count"),
            _count(SearchQuery, SearchQuery.is_follow_up.is_(True)).label("follow_up_count"),
        )
        .where(*filters)
        .order_by(desc(Research.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    total = (await db.execute(select(func.count(Research.id)).where(*filters))).scalar_one()
    items = [
        ResearchSummaryResponse(
            **ResearchBasicResponse.model_validate(row.Research).model_dump(),
            report_title=row.report_title,
            executive_summary=row.executive_summary,
            source_count=row.source_count or 0,
            claim_count=row.claim_count or 0,
            contradiction_count=row.contradiction_count or 0,
            follow_up_count=row.follow_up_count or 0,
        )
        for row in rows
    ]
    return ResearchListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{research_id}", response_model=ResearchDetailResponse)
async def get_research_detail(research_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_detail(db, research_id)


@router.post("/{research_id}/rerun", response_model=ResearchBasicResponse, status_code=status.HTTP_201_CREATED)
async def rerun_research(research_id: str, db: AsyncSession = Depends(get_db)):
    old = await _get_research(db, research_id)
    research = Research(question=old.question, depth=old.depth, domain=old.domain, status=ResearchStatus.CREATED)
    db.add(research)
    await db.commit()
    start_pipeline(research.id)
    return research


@router.post("/{research_id}/cancel", response_model=ResearchBasicResponse)
async def cancel_research(research_id: str, db: AsyncSession = Depends(get_db)):
    research = await _get_research(db, research_id)
    if research.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"Research is not running (status: {research.status.value})")
    research.status = ResearchStatus.CANCELLED
    await db.commit()
    if not task_manager.cancel(research_id):
        # Not running in this process: the pipeline (if any) stops at its next
        # checkpoint; record the event now so streams terminate cleanly.
        last = (await db.execute(select(func.max(ResearchEvent.seq)).where(ResearchEvent.research_id == research_id))).scalar()
        db.add(
            ResearchEvent(
                research_id=research_id, seq=(last or 0) + 1, event_type="research.cancelled", agent="orchestrator", data={}
            )
        )
        await db.commit()
        event_bus.publish(research_id)
    return research


@router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research(research_id: str, db: AsyncSession = Depends(get_db)):
    research = await _get_research(db, research_id)
    if task_manager.cancel(research_id):
        try:
            await asyncio.wait_for(task_manager.wait(research_id), timeout=5)
        except TimeoutError:
            pass
    await db.delete(research)
    await db.commit()
    event_bus.publish(research_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{research_id}/resynthesize", response_model=ResearchBasicResponse, status_code=status.HTTP_202_ACCEPTED)
async def resynthesize_research(research_id: str, db: AsyncSession = Depends(get_db)):
    """Re-verify and rewrite the report from the current (non-excluded) sources."""
    research = await _get_research(db, research_id)
    if research.status not in TERMINAL_STATUSES or task_manager.is_running(research_id):
        raise HTTPException(status_code=409, detail="Research is still running")
    usable = (
        await db.execute(select(func.count(Source.id)).where(Source.research_id == research_id, Source.is_excluded.is_(False)))
    ).scalar_one()
    if not usable:
        raise HTTPException(status_code=400, detail="Every source is excluded: include at least one source first")
    research.status = ResearchStatus.VERIFYING
    research.error_message = None
    await db.commit()
    start_pipeline(research_id, mode="resynthesize")
    return research


async def _set_excluded(db: AsyncSession, research_id: str, source_id: str, excluded: bool) -> Source:
    source = (
        await db.execute(select(Source).where(Source.id == source_id, Source.research_id == research_id))
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_excluded = excluded
    await db.commit()
    return source


@router.post("/{research_id}/sources/{source_id}/exclude", response_model=SourceSchema)
async def exclude_source(research_id: str, source_id: str, db: AsyncSession = Depends(get_db)):
    return await _set_excluded(db, research_id, source_id, True)


@router.post("/{research_id}/sources/{source_id}/include", response_model=SourceSchema)
async def include_source(research_id: str, source_id: str, db: AsyncSession = Depends(get_db)):
    return await _set_excluded(db, research_id, source_id, False)


@router.get("/{research_id}/sources/{source_id}", response_model=SourceDetailSchema)
async def get_source(research_id: str, source_id: str, db: AsyncSession = Depends(get_db)):
    source = (
        await db.execute(select(Source).where(Source.id == source_id, Source.research_id == research_id))
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/{research_id}/events")
async def stream_research_events(
    research_id: str,
    request: Request,
    after: int = Query(0, ge=0, description="Only send events with a sequence number above this one"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """Server-Sent Events: replays stored events, then streams new ones until
    the research reaches a terminal state. Reconnections resume after the
    last received event (standard ``Last-Event-ID`` header)."""
    async with AsyncSessionLocal() as db:
        await _get_research(db, research_id)
    start_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

    async def event_generator() -> AsyncGenerator[str, None]:
        last_seq = start_seq
        last_write = time.monotonic()
        yield "retry: 3000\n\n"
        async with event_bus.subscribe(research_id) as wake:
            while True:
                if await request.is_disconnected():
                    return
                wake.clear()
                async with AsyncSessionLocal() as db:
                    # Status first: a terminal status is committed together with
                    # its final event, so everything is visible below.
                    current = (await db.execute(select(Research.status).where(Research.id == research_id))).scalar_one_or_none()
                    events = (
                        (
                            await db.execute(
                                select(ResearchEvent)
                                .where(ResearchEvent.research_id == research_id, ResearchEvent.seq > last_seq)
                                .order_by(ResearchEvent.seq)
                            )
                        )
                        .scalars()
                        .all()
                    )
                for event in events:
                    last_seq = event.seq
                    payload = ResearchEventSchema.model_validate(event).model_dump(mode="json")
                    payload["status"] = current.value if current else None
                    yield f"id: {event.seq}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    last_write = time.monotonic()
                if current is None or current in TERMINAL_STATUSES:
                    end = {"status": current.value if current else "deleted"}
                    yield f"event: end\ndata: {json.dumps(end)}\n\n"
                    return
                if time.monotonic() - last_write > KEEPALIVE_SECONDS:
                    yield ": keep-alive\n\n"
                    last_write = time.monotonic()
                try:
                    await asyncio.wait_for(wake.wait(), timeout=POLL_SECONDS)
                except TimeoutError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text).lower()).strip("-")[:60] or "research"


def build_markdown_export(research: Research) -> str:
    report = research.report
    lines = [report.markdown_content.rstrip() if report else f"# {research.question}\n\n_No report was generated._"]
    citations = report.citations if report else []
    if citations:
        lines += ["", "## Sources", ""]
        for c in citations:
            note = "" if c.get("cited", True) else " (consulted, not cited)"
            lines.append(f"{c['index']}. [{c['title']}]({c['url']}) — {c.get('domain', '')}{note}")
    excluded = [s for s in research.sources if s.is_excluded]
    if excluded:
        lines += ["", "### Excluded sources", ""] + [f"- ~~{s.title}~~ ({s.url})" for s in excluded]
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines += [
        "",
        "---",
        f"_Question: {research.question}_  ",
        f"_Profile: {research.domain.value} · depth: {research.depth.value} · {len(research.sources)} sources · "
        f"{research.llm_calls} LLM calls · {research.tokens_used} tokens · exported {generated} by AI Research Agent_",
    ]
    return "\n".join(lines) + "\n"


@router.get("/{research_id}/export")
async def export_research(
    research_id: str,
    format: str = Query("md", pattern="^(md|json)$"),
    db: AsyncSession = Depends(get_db),
):
    research = await _get_detail(db, research_id)
    name = _slug(research.report.title if research.report else research.question)
    if format == "json":
        body = ResearchDetailResponse.model_validate(research).model_dump_json(indent=2)
        media_type, filename = "application/json", f"{name}.json"
    else:
        body = build_markdown_export(research)
        media_type, filename = "text/markdown; charset=utf-8", f"{name}.md"
    return Response(content=body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# Narrow read endpoints kept for API consumers.


@router.get("/{research_id}/sources", response_model=list[SourceSchema])
async def get_research_sources(research_id: str, db: AsyncSession = Depends(get_db)):
    await _get_research(db, research_id)
    stmt = (
        select(Source)
        .where(Source.research_id == research_id, Source.is_excluded.is_(False))
        .order_by(desc(Source.relevance_score))
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/{research_id}/claims", response_model=list[ClaimSchema])
async def get_research_claims(research_id: str, db: AsyncSession = Depends(get_db)):
    await _get_research(db, research_id)
    return (await db.execute(select(Claim).where(Claim.research_id == research_id).order_by(Claim.created_at))).scalars().all()


@router.get("/{research_id}/contradictions", response_model=list[ContradictionSchema])
async def get_research_contradictions(research_id: str, db: AsyncSession = Depends(get_db)):
    await _get_research(db, research_id)
    stmt = select(Contradiction).where(Contradiction.research_id == research_id).order_by(Contradiction.created_at)
    return (await db.execute(stmt)).scalars().all()


@router.get("/{research_id}/report", response_model=ReportSchema)
async def get_research_report(research_id: str, db: AsyncSession = Depends(get_db)):
    await _get_research(db, research_id)
    report = (await db.execute(select(Report).where(Report.research_id == research_id))).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not ready")
    return report
