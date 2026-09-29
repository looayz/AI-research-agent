import asyncio
import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from app.agents.base import AgentOutputError, MeteredLLM
from app.agents.evidence import EvidenceSource
from app.agents.gap_analyzer.agent import GapAnalyzerAgent
from app.agents.planner.agent import PlannerAgent
from app.agents.researcher.agent import CollectedSource, ResearcherAgent
from app.agents.synthesizer.agent import SynthesizerAgent
from app.agents.verifier.agent import VerificationResult, VerifierAgent
from app.core.config import settings
from app.core.database import AsyncSessionLocal, utcnow
from app.core.text import clip, detect_language
from app.models.research import (
    TERMINAL_STATUSES,
    Claim,
    Contradiction,
    Report,
    Research,
    ResearchEvent,
    ResearchPlan,
    ResearchStatus,
    SearchQuery,
    Source,
)
from app.providers.llm.base import LLMError, LLMProvider
from app.providers.llm.factory import get_llm_provider
from app.providers.search.base import SearchError, SearchProvider
from app.providers.search.factory import get_search_provider
from app.services.event_bus import event_bus
from app.services.fetcher import SafeFetcher
from app.services.semantic_memory import SemanticMemoryService

logger = logging.getLogger(__name__)

# Gap-analysis rounds (each may trigger follow-up searches and a re-verification)
FOLLOW_UP_ROUNDS = {"quick": 0, "standard": 1, "deep": 3}
# Most relevant sources handed to the verifier and the synthesizer
EVIDENCE_LIMITS = {"quick": 8, "standard": 12, "deep": 16}
RESULTS_PER_QUERY = {"quick": 3, "standard": 4, "deep": 5}
FOLLOW_UP_RESULTS_PER_QUERY = 3

DEMO_NOTE = {
    "en": (
        "Demo mode: sources and analysis are synthetic (mock providers). "
        "Configure a real LLM and search provider for actual research."
    ),
    "fr": (
        "Mode démo : sources et analyse synthétiques (fournisseurs fictifs). "
        "Configurez un vrai LLM et un vrai moteur de recherche pour une recherche réelle."
    ),
}
INTERRUPTED_MESSAGE = "Interrupted: the server stopped while this research was running. Use rerun to start it again."


class ResearchCancelled(Exception):
    pass


class ResearchTimeout(Exception):
    pass


@dataclass
class _Usage:
    search_calls: int = 0
    fetch_calls: int = 0


@dataclass
class RunContext:
    db: AsyncSession
    research: Research
    started: float
    mode: str
    base: dict = field(default_factory=dict)
    seq: int = 0
    sub_questions: list[str] = field(default_factory=list)
    plan_queries: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    verification: VerificationResult = field(default_factory=VerificationResult)
    gaps: list[str] = field(default_factory=list)
    queries_run: list[str] = field(default_factory=list)

    @property
    def rid(self) -> str:
        return self.research.id

    @property
    def depth(self) -> str:
        return self.research.depth.value

    @property
    def domain(self) -> str:
        return self.research.domain.value


def describe_error(exc: BaseException) -> str:
    if isinstance(exc, (LLMError, SearchError, ResearchTimeout)):
        return clip(str(exc), 500)
    return clip(f"{type(exc).__name__}: {exc}", 500)


async def _max_seq(db: AsyncSession, research_id: str) -> int:
    return (await db.execute(select(func.max(ResearchEvent.seq)).where(ResearchEvent.research_id == research_id))).scalar() or 0


async def recover_interrupted_researches(session_factory: async_sessionmaker = AsyncSessionLocal) -> int:
    """Mark researches left running by a previous process as failed.

    Without this, a restart mid-research leaves them "running" forever and
    their event streams never end.
    """
    async with session_factory() as db:
        stuck = (await db.execute(select(Research).where(Research.status.not_in(TERMINAL_STATUSES)))).scalars().all()
        for research in stuck:
            research.status = ResearchStatus.FAILED
            research.error_message = INTERRUPTED_MESSAGE
            db.add(
                ResearchEvent(
                    research_id=research.id,
                    seq=await _max_seq(db, research.id) + 1,
                    event_type="research.failed",
                    agent="orchestrator",
                    data={"error": INTERRUPTED_MESSAGE},
                )
            )
        await db.commit()
    return len(stuck)


class ResearchOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker = AsyncSessionLocal,
        llm: Optional[LLMProvider] = None,
        search: Optional[SearchProvider] = None,
        fetcher_factory: Callable[[], SafeFetcher] = SafeFetcher,
    ):
        self.session_factory = session_factory
        self._llm = llm
        self._search = search
        self.fetcher_factory = fetcher_factory
        self.usage = _Usage()

    def _build_agents(self) -> None:
        self.llm = MeteredLLM(self._llm or get_llm_provider())
        self.search = self._search or get_search_provider()
        self.planner = PlannerAgent(self.llm)
        self.researcher = ResearcherAgent(self.search, fetcher_factory=self.fetcher_factory)
        self.verifier = VerifierAgent(self.llm)
        self.gap_analyzer = GapAnalyzerAgent(self.llm)
        self.synthesizer = SynthesizerAgent(self.llm)

    @property
    def demo_mode(self) -> bool:
        return self.llm.name == "mock" or "mock" in self.search.name.split("+")

    # ------------------------------------------------------------------ run

    async def run(self, research_id: str, mode: str = "full") -> None:
        """Run the pipeline. ``mode="resynthesize"`` re-verifies and rewrites the
        report from the current (non-excluded) sources without searching again."""
        started = time.monotonic()
        base: dict = {}
        try:
            async with self.session_factory() as db:
                research = await db.get(Research, research_id)
                if research is None:
                    return
                base = {
                    "runtime": research.runtime_seconds if mode == "resynthesize" else 0.0,
                    "llm_calls": research.llm_calls if mode == "resynthesize" else 0,
                    "tokens": research.tokens_used if mode == "resynthesize" else 0,
                    "search_calls": research.search_calls if mode == "resynthesize" else 0,
                    "fetch_calls": research.fetch_calls if mode == "resynthesize" else 0,
                }
                ctx = RunContext(db=db, research=research, started=started, mode=mode, base=base)
                ctx.seq = await _max_seq(db, research_id)
                self._build_agents()
                try:
                    await asyncio.wait_for(self._execute(ctx), timeout=settings.MAX_RUNTIME_SECONDS)
                except TimeoutError as exc:
                    raise ResearchTimeout(
                        f"Runtime limit exceeded ({settings.MAX_RUNTIME_SECONDS}s, see MAX_RUNTIME_SECONDS)"
                    ) from exc
        except ResearchCancelled:
            await self._finalize(research_id, ResearchStatus.CANCELLED, None, started, base)
        except asyncio.CancelledError:
            # Task cancelled: by the user (status already CANCELLED) or by a shutdown.
            await self._finalize(research_id, ResearchStatus.FAILED, INTERRUPTED_MESSAGE, started, base)
            raise
        except Exception as exc:
            if not isinstance(exc, (LLMError, SearchError, ResearchTimeout)):
                logger.exception("Research %s failed", research_id)
            await self._finalize(research_id, ResearchStatus.FAILED, describe_error(exc), started, base)

    async def _execute(self, ctx: RunContext) -> None:
        await self._emit(
            ctx,
            "research.started",
            "orchestrator",
            {
                "mode": ctx.mode,
                "question": ctx.research.question,
                "depth": ctx.depth,
                "domain": ctx.domain,
                "llm": f"{self.llm.name}/{self.llm.model}",
                "search": self.search.name,
            },
        )
        if ctx.mode == "resynthesize":
            await self._load_existing(ctx)
            await self._verify(ctx)
        else:
            await self._plan(ctx)
            await self._recall_memory(ctx)
            await self._search_round(ctx, ctx.plan_queries, iteration=0, origin="search")
            if not [s for s in ctx.sources if not s.is_excluded]:
                raise SearchError(
                    "No usable sources were found. Rephrase the question or check the search provider configuration."
                )
            await self._verify(ctx)
            await self._gap_loop(ctx)
        await self._synthesize(ctx)
        await self._complete(ctx)

    # ------------------------------------------------------------- helpers

    def _sync_usage(self, ctx: RunContext) -> None:
        r = ctx.research
        r.llm_calls = ctx.base["llm_calls"] + self.llm.calls
        r.tokens_used = ctx.base["tokens"] + self.llm.tokens
        r.search_calls = ctx.base["search_calls"] + self.usage.search_calls
        r.fetch_calls = ctx.base["fetch_calls"] + self.usage.fetch_calls
        r.runtime_seconds = round(ctx.base["runtime"] + time.monotonic() - ctx.started, 2)

    async def _emit(self, ctx: RunContext, event_type: str, agent: str, data: dict[str, Any]) -> None:
        self._sync_usage(ctx)
        ctx.seq += 1
        ctx.db.add(ResearchEvent(research_id=ctx.rid, seq=ctx.seq, event_type=event_type, agent=agent, data=data))
        await ctx.db.commit()
        event_bus.publish(ctx.rid)

    async def _warn(self, ctx: RunContext, agent: str, message: str) -> None:
        logger.warning("Research %s: %s", ctx.rid, message)
        await self._emit(ctx, "warning", agent, {"message": message})

    async def _checkpoint(self, ctx: RunContext) -> None:
        if time.monotonic() - ctx.started > settings.MAX_RUNTIME_SECONDS:
            raise ResearchTimeout(f"Runtime limit exceeded ({settings.MAX_RUNTIME_SECONDS}s, see MAX_RUNTIME_SECONDS)")
        status = (await ctx.db.execute(select(Research.status).where(Research.id == ctx.rid))).scalar_one_or_none()
        if status is None or status == ResearchStatus.CANCELLED:
            raise ResearchCancelled()

    async def _set_status(self, ctx: RunContext, status: ResearchStatus) -> None:
        await self._checkpoint(ctx)
        # Conditional update: a cancellation written by another request always wins.
        result = await ctx.db.execute(
            update(Research)
            .where(Research.id == ctx.rid, Research.status != ResearchStatus.CANCELLED)
            .values(status=status, updated_at=utcnow()),
            execution_options={"synchronize_session": False},
        )
        if result.rowcount == 0:
            raise ResearchCancelled()
        set_committed_value(ctx.research, "status", status)
        await ctx.db.commit()

    def _evidence(self, ctx: RunContext) -> list[EvidenceSource]:
        usable = sorted((s for s in ctx.sources if not s.is_excluded), key=lambda s: s.relevance_score, reverse=True)
        return [EvidenceSource.model_validate(s) for s in usable[: EVIDENCE_LIMITS.get(ctx.depth, 12)]]

    # -------------------------------------------------------------- phases

    async def _plan(self, ctx: RunContext) -> None:
        await self._set_status(ctx, ResearchStatus.PLANNING)
        await self._emit(ctx, "planner.started", "planner", {"depth": ctx.depth, "domain": ctx.domain})
        fallback = False
        try:
            plan = await self.planner.create_plan(ctx.research.question, domain=ctx.domain, depth=ctx.depth)
        except AgentOutputError as exc:
            fallback = True
            plan = PlannerAgent.fallback_plan(ctx.research.question, ctx.depth)
            await self._warn(ctx, "planner", f"Planner output was unusable ({exc}); searching for the question itself.")
        ctx.db.add(
            ResearchPlan(
                research_id=ctx.rid,
                objective=plan.objective,
                sub_questions=plan.sub_questions,
                search_queries=plan.search_queries,
                research_scope=plan.research_scope,
                constraints=plan.constraints,
            )
        )
        ctx.sub_questions = plan.sub_questions
        ctx.plan_queries = plan.search_queries
        await self._emit(
            ctx,
            "planner.completed",
            "planner",
            {
                "objective": plan.objective,
                "sub_questions": plan.sub_questions,
                "queries": plan.search_queries,
                "fallback": fallback,
            },
        )

    async def _recall_memory(self, ctx: RunContext) -> None:
        if not settings.MEMORY_RECALL_ENABLED:
            return
        await self._set_status(ctx, ResearchStatus.SEARCHING)
        matches = await SemanticMemoryService.find_relevant_past_sources(
            db=ctx.db,
            query=ctx.research.question,
            threshold=settings.MEMORY_RECALL_THRESHOLD,
            limit=settings.MEMORY_RECALL_LIMIT,
            exclude_research_id=ctx.rid,
        )
        if not matches:
            return
        for past, similarity in matches:
            row = Source(
                research_id=ctx.rid,
                url=past.url,
                title=past.title,
                domain=past.domain,
                published_at=past.published_at,
                content=past.content,
                source_type=past.source_type,
                relevance_score=round(0.6 * past.relevance_score + 0.4 * similarity, 3),
                evaluation_factors={
                    **{k: v for k, v in (past.evaluation_factors or {}).items() if not k.startswith("memory_")},
                    "memory_similarity": similarity,
                    "memory_from_research": past.research_id,
                },
                evaluation_notes=[f"Recalled from a previous investigation (similarity {similarity:.2f})"],
                embedding=past.embedding,
                origin="memory",
                fetch_status=past.fetch_status or "ok",
            )
            ctx.db.add(row)
            ctx.sources.append(row)
        await self._emit(
            ctx,
            "memory.recalled",
            "memory",
            {
                "count": len(matches),
                "matches": [{"title": s.title, "url": s.url, "similarity": sim} for s, sim in matches],
            },
        )

    async def _search_round(self, ctx: RunContext, queries: list[str], *, iteration: int, origin: str) -> int:
        await self._set_status(ctx, ResearchStatus.SEARCHING)
        await self._emit(ctx, "search.started", "researcher", {"iteration": iteration, "queries": queries})
        remaining = settings.MAX_SOURCES - len(ctx.sources)
        if remaining <= 0:
            await self._warn(ctx, "researcher", f"Source limit reached ({settings.MAX_SOURCES}, see MAX_SOURCES).")
            return 0

        per_query = RESULTS_PER_QUERY.get(ctx.depth, 4) if iteration == 0 else FOLLOW_UP_RESULTS_PER_QUERY
        result = await self.researcher.collect(
            queries,
            question=ctx.research.question,
            research_domain=ctx.domain,
            max_per_query=per_query,
            max_new_sources=min(remaining, per_query * len(queries)),
            known_urls={s.url for s in ctx.sources},
            origin=origin,
        )
        self.usage.search_calls += result.search_calls
        self.usage.fetch_calls += result.fetch_calls
        for query in queries:
            ctx.db.add(
                SearchQuery(
                    research_id=ctx.rid,
                    query=clip(query, 500),
                    results_count=result.results_per_query.get(query, 0),
                    is_follow_up=iteration > 0,
                    iteration=iteration,
                )
            )
        for collected in result.sources:
            row = self._source_row(ctx.rid, collected)
            ctx.db.add(row)
            ctx.sources.append(row)
        ctx.queries_run.extend(queries)

        await self._emit(
            ctx,
            "search.completed",
            "researcher",
            {
                "iteration": iteration,
                "results": sum(result.results_per_query.values()),
                "new_sources": len(result.sources),
                "total_sources": len(ctx.sources),
                "failed_fetches": result.failed_fetches,
                "errors": result.errors[:3],
            },
        )
        if result.errors and len(result.errors) == len(queries):
            if iteration == 0 and not ctx.sources:
                raise SearchError(f"Every search failed: {result.errors[0]}")
            await self._warn(ctx, "researcher", f"Searches failed: {result.errors[0]}")
        return len(result.sources)

    @staticmethod
    def _source_row(research_id: str, collected: CollectedSource) -> Source:
        return Source(
            research_id=research_id,
            url=collected.url,
            title=collected.title,
            domain=clip(collected.domain, 255),
            published_at=collected.published_at,
            retrieved_at=collected.retrieved_at,
            content=collected.content,
            source_type=clip(collected.source_type, 50),
            relevance_score=collected.relevance_score,
            evaluation_factors=collected.evaluation_factors,
            evaluation_notes=collected.evaluation_notes,
            embedding=collected.embedding,
            origin=collected.origin,
            origin_query=collected.origin_query,
            fetch_status=collected.fetch_status,
        )

    async def _verify(self, ctx: RunContext) -> None:
        await self._set_status(ctx, ResearchStatus.VERIFYING)
        evidence = self._evidence(ctx)
        await self._emit(ctx, "verifier.started", "verifier", {"sources": len(evidence)})
        try:
            result = await self.verifier.verify(ctx.research.question, evidence, depth=ctx.depth)
        except AgentOutputError as exc:
            await self._warn(ctx, "verifier", f"Verifier output was unusable ({exc}); the report relies on the sources only.")
            result = VerificationResult()
        ctx.verification = result

        await ctx.db.execute(delete(Claim).where(Claim.research_id == ctx.rid))
        await ctx.db.execute(delete(Contradiction).where(Contradiction.research_id == ctx.rid))
        for claim in result.claims:
            ctx.db.add(
                Claim(
                    research_id=ctx.rid,
                    claim_text=claim.claim_text,
                    status=claim.status,
                    confidence=claim.confidence,
                    supporting_sources=claim.supporting_sources,
                    contradicting_sources=claim.contradicting_sources,
                    reasoning=claim.reasoning,
                )
            )
        for item in result.contradictions:
            ctx.db.add(
                Contradiction(
                    research_id=ctx.rid,
                    topic=clip(item.topic, 255),
                    point_a=item.point_a,
                    source_a_url=item.source_a_url,
                    point_b=item.point_b,
                    source_b_url=item.source_b_url,
                    explanation=item.explanation,
                )
            )
        await self._emit(
            ctx,
            "verifier.completed",
            "verifier",
            {
                "claims": len(result.claims),
                "contradictions": len(result.contradictions),
                "by_status": dict(Counter(c.status.value for c in result.claims)),
            },
        )

    async def _gap_loop(self, ctx: RunContext) -> None:
        max_rounds = FOLLOW_UP_ROUNDS.get(ctx.depth, 1)
        for round_number in range(1, max_rounds + 1):
            await self._set_status(ctx, ResearchStatus.ANALYZING)
            await self._emit(ctx, "gap_analyzer.started", "gap_analyzer", {"round": round_number, "max_rounds": max_rounds})
            try:
                gap = await self.gap_analyzer.analyze_gaps(
                    ctx.research.question,
                    ctx.verification.claims,
                    contradictions=ctx.verification.contradictions,
                    sub_questions=ctx.sub_questions,
                    previous_queries=ctx.queries_run,
                    round_number=round_number,
                    max_rounds=max_rounds,
                    max_queries=settings.MAX_FOLLOW_UP_SEARCHES,
                )
            except (AgentOutputError, LLMError) as exc:
                await self._warn(ctx, "gap_analyzer", f"Gap analysis failed ({exc}); continuing with the current evidence.")
                return
            ctx.gaps = gap.gaps_identified
            await self._emit(
                ctx,
                "gap_analyzer.completed",
                "gap_analyzer",
                {
                    "round": round_number,
                    "sufficient": gap.is_sufficient,
                    "gaps": gap.gaps_identified,
                    "follow_up_queries": gap.follow_up_queries,
                },
            )
            if gap.is_sufficient or not gap.follow_up_queries:
                return
            new_sources = await self._search_round(ctx, gap.follow_up_queries, iteration=round_number, origin="follow_up")
            if new_sources == 0:
                await self._warn(ctx, "researcher", "Follow-up searches returned no new sources.")
                return
            await self._verify(ctx)

    async def _load_existing(self, ctx: RunContext) -> None:
        ctx.sources = list((await ctx.db.execute(select(Source).where(Source.research_id == ctx.rid))).scalars())
        plan = (await ctx.db.execute(select(ResearchPlan).where(ResearchPlan.research_id == ctx.rid))).scalar_one_or_none()
        ctx.sub_questions = list(plan.sub_questions) if plan else []
        queries = (await ctx.db.execute(select(SearchQuery.query).where(SearchQuery.research_id == ctx.rid))).scalars()
        ctx.queries_run = list(queries)
        if not [s for s in ctx.sources if not s.is_excluded]:
            raise SearchError("Every source is excluded: include at least one source to regenerate the report.")

    async def _synthesize(self, ctx: RunContext) -> None:
        await self._set_status(ctx, ResearchStatus.SYNTHESIZING)
        evidence = self._evidence(ctx)
        await self._emit(ctx, "synthesizer.started", "synthesizer", {"sources": len(evidence)})
        report = await self.synthesizer.generate_report(
            ctx.research.question,
            evidence,
            domain=ctx.domain,
            claims=ctx.verification.claims,
            contradictions=ctx.verification.contradictions,
            gaps=ctx.gaps,
        )
        limitations = list(report.limitations)
        if self.demo_mode and not any("demo" in item.lower() or "démo" in item.lower() for item in limitations):
            limitations.insert(0, DEMO_NOTE[detect_language(ctx.research.question)])
        await ctx.db.execute(delete(Report).where(Report.research_id == ctx.rid))
        ctx.db.add(
            Report(
                research_id=ctx.rid,
                title=clip(report.title, 255),
                markdown_content=report.markdown_content,
                executive_summary=report.executive_summary,
                limitations=limitations,
                citations=report.citations,
            )
        )
        await self._emit(
            ctx,
            "synthesizer.completed",
            "synthesizer",
            {
                "title": report.title,
                "cited_sources": sum(1 for c in report.citations if c["cited"]),
                "words": len(report.markdown_content.split()),
            },
        )

    async def _complete(self, ctx: RunContext) -> None:
        await self._checkpoint(ctx)
        self._sync_usage(ctx)
        result = await ctx.db.execute(
            update(Research)
            .where(Research.id == ctx.rid, Research.status != ResearchStatus.CANCELLED)
            .values(status=ResearchStatus.COMPLETED, completed_at=utcnow(), error_message=None, updated_at=utcnow()),
            execution_options={"synchronize_session": False},
        )
        if result.rowcount == 0:
            raise ResearchCancelled()
        set_committed_value(ctx.research, "status", ResearchStatus.COMPLETED)
        ctx.seq += 1
        ctx.db.add(
            ResearchEvent(
                research_id=ctx.rid,
                seq=ctx.seq,
                event_type="research.completed",
                agent="orchestrator",
                data={
                    "runtime_seconds": ctx.research.runtime_seconds,
                    "tokens_used": ctx.research.tokens_used,
                    "llm_calls": ctx.research.llm_calls,
                    "sources": len(ctx.sources),
                    "claims": len(ctx.verification.claims),
                },
            )
        )
        await ctx.db.commit()
        event_bus.publish(ctx.rid)

    async def _finalize(self, research_id: str, status: ResearchStatus, error: Optional[str], started: float, base: dict) -> None:
        """Record a terminal failure/cancellation in a fresh session (the run's
        session may be unusable after an error or a cancellation)."""
        try:
            async with self.session_factory() as db:
                research = await db.get(Research, research_id)
                if research is None:
                    return
                if research.status == ResearchStatus.CANCELLED:
                    status, error = ResearchStatus.CANCELLED, None
                elif research.status in TERMINAL_STATUSES:
                    return
                research.status = status
                research.error_message = error
                research.runtime_seconds = round(base.get("runtime", 0.0) + time.monotonic() - started, 2)
                if hasattr(self, "llm"):
                    research.llm_calls = base.get("llm_calls", 0) + self.llm.calls
                    research.tokens_used = base.get("tokens", 0) + self.llm.tokens
                    research.search_calls = base.get("search_calls", 0) + self.usage.search_calls
                    research.fetch_calls = base.get("fetch_calls", 0) + self.usage.fetch_calls
                db.add(
                    ResearchEvent(
                        research_id=research_id,
                        seq=await _max_seq(db, research_id) + 1,
                        event_type="research.cancelled" if status == ResearchStatus.CANCELLED else "research.failed",
                        agent="orchestrator",
                        data={} if status == ResearchStatus.CANCELLED else {"error": error},
                    )
                )
                await db.commit()
        except Exception:  # noqa: BLE001 - never let bookkeeping mask the original problem
            logger.exception("Could not record the final state of research %s", research_id)
        event_bus.publish(research_id)
