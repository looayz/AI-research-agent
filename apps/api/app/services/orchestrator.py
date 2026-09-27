import time
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.research import (
    Research,
    ResearchStatus,
    ResearchDepth,
    ResearchDomain,
    ResearchPlan,
    SearchQuery,
    Source,
    Claim,
    Contradiction,
    ResearchEvent,
    Report,
)
from app.providers.llm.factory import get_llm_provider
from app.providers.search.factory import get_search_provider
from app.agents.planner.agent import PlannerAgent
from app.agents.researcher.agent import ResearcherAgent, CollectedSource
from app.agents.verifier.agent import VerifierAgent
from app.agents.gap_analyzer.agent import GapAnalyzerAgent
from app.agents.synthesizer.agent import SynthesizerAgent
from app.services.semantic_memory import SemanticMemoryService


class ResearchOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.search = get_search_provider()

        self.planner = PlannerAgent(self.llm)
        self.researcher = ResearcherAgent(self.search)
        self.verifier = VerifierAgent(self.llm)
        self.gap_analyzer = GapAnalyzerAgent(self.llm)
        self.synthesizer = SynthesizerAgent(self.llm)

    async def _emit_event(self, research_id: str, event_type: str, agent: str, data: dict):
        event = ResearchEvent(
            research_id=research_id,
            event_type=event_type,
            agent=agent,
            data=data,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(event)
        await self.db.commit()

    async def run_pipeline(self, research_id: str) -> Research:
        start_time = time.time()

        stmt = select(Research).where(Research.id == research_id)
        res = await self.db.execute(stmt)
        research = res.scalar_one_or_none()
        if not research:
            raise ValueError(f"Research with ID {research_id} not found")

        domain_str = research.domain.value if hasattr(research.domain, "value") else str(research.domain)

        try:
            # 1. Planning phase
            research.status = ResearchStatus.PLANNING
            await self.db.commit()
            await self._emit_event(research_id, "planner.started", "planner", {
                "question": research.question,
                "domain": domain_str
            })

            plan_schema = await self.planner.create_plan(research.question, domain=domain_str)
            plan = ResearchPlan(
                research_id=research.id,
                objective=plan_schema.objective,
                sub_questions=plan_schema.sub_questions,
                search_queries=plan_schema.search_queries,
                research_scope=plan_schema.research_scope,
                constraints=plan_schema.constraints
            )
            self.db.add(plan)
            research.llm_calls += 1
            await self.db.commit()
            await self._emit_event(research_id, "planner.completed", "planner", {"queries": plan_schema.search_queries})

            # 2. Semantic Memory Query (Cross-Research Reuse)
            memory_sources_found = await SemanticMemoryService.find_relevant_past_sources(
                db=self.db,
                query=research.question,
                threshold=0.6,
                limit=3
            )
            reused_collected_sources: list[CollectedSource] = []
            if memory_sources_found:
                await self._emit_event(research_id, "semantic_memory.matched", "semantic_memory", {
                    "matched_count": len(memory_sources_found),
                    "matches": [{"title": s.title, "similarity": sim} for s, sim in memory_sources_found]
                })
                for past_src, sim in memory_sources_found:
                    reused_collected_sources.append(
                        CollectedSource(
                            url=past_src.url,
                            title=f"[Reused Memory] {past_src.title}",
                            domain=past_src.domain,
                            published_at=past_src.published_at,
                            retrieved_at=datetime.now(timezone.utc),
                            content=past_src.content,
                            source_type=past_src.source_type,
                            relevance_score=round(past_src.relevance_score * sim, 2),
                            evaluation_factors={"memory_similarity": sim},
                            evaluation_notes=["Source recalled from semantic repository memory"],
                            embedding=past_src.embedding
                        )
                    )

            # 3. Initial Searching & Fetching phase
            research.status = ResearchStatus.SEARCHING
            await self.db.commit()
            await self._emit_event(research_id, "search.started", "researcher", {
                "count": len(plan_schema.search_queries),
                "domain": domain_str
            })

            for q_text in plan_schema.search_queries:
                q_model = SearchQuery(
                    research_id=research.id,
                    query=q_text,
                    results_count=0,
                    is_follow_up=False
                )
                self.db.add(q_model)
            await self.db.commit()

            live_sources = await self.researcher.execute_searches(
                plan_schema.search_queries,
                research_domain=domain_str
            )
            research.search_calls += len(plan_schema.search_queries)
            research.fetch_calls += len(live_sources)

            collected_sources = reused_collected_sources + live_sources

            for cs in collected_sources:
                source_model = Source(
                    research_id=research.id,
                    url=cs.url,
                    title=cs.title,
                    domain=cs.domain,
                    published_at=cs.published_at,
                    retrieved_at=cs.retrieved_at,
                    content=cs.content,
                    source_type=cs.source_type,
                    relevance_score=cs.relevance_score,
                    evaluation_factors=cs.evaluation_factors,
                    evaluation_notes=cs.evaluation_notes,
                    embedding=cs.embedding
                )
                self.db.add(source_model)
            await self.db.commit()
            await self._emit_event(research_id, "sources.collected", "researcher", {
                "total_sources": len(collected_sources),
                "reused_from_memory": len(reused_collected_sources)
            })

            # 4. Verification phase
            research.status = ResearchStatus.VERIFYING
            await self.db.commit()
            await self._emit_event(research_id, "verifier.started", "verifier", {"sources_to_verify": len(collected_sources)})

            verification_result = await self.verifier.verify(research.question, collected_sources)
            research.llm_calls += 1

            for c in verification_result.claims:
                claim_model = Claim(
                    research_id=research.id,
                    claim_text=c.claim_text,
                    status=c.status,
                    confidence=c.confidence,
                    supporting_sources=c.supporting_sources,
                    contradicting_sources=c.contradicting_sources,
                    reasoning=c.reasoning
                )
                self.db.add(claim_model)

            for d in verification_result.contradictions:
                contradiction_model = Contradiction(
                    research_id=research.id,
                    topic=d.topic,
                    point_a=d.point_a,
                    source_a_url=d.source_a_url,
                    point_b=d.point_b,
                    source_b_url=d.source_b_url,
                    explanation=d.explanation
                )
                self.db.add(contradiction_model)

            await self.db.commit()
            await self._emit_event(research_id, "verifier.completed", "verifier", {
                "claims_count": len(verification_result.claims),
                "contradictions_count": len(verification_result.contradictions)
            })

            # 5. Deep Research Loop: Gap Analysis & Follow-up Searches
            if research.depth in (ResearchDepth.STANDARD, ResearchDepth.DEEP):
                await self._emit_event(research_id, "gap_analyzer.started", "gap_analyzer", {})
                gap_analysis = await self.gap_analyzer.analyze_gaps(
                    question=research.question,
                    claims=verification_result.claims,
                    current_depth=research.depth.value
                )
                research.llm_calls += 1

                if not gap_analysis.is_sufficient and gap_analysis.follow_up_queries:
                    await self._emit_event(research_id, "follow_up.started", "researcher", {
                        "queries": gap_analysis.follow_up_queries,
                        "gaps": gap_analysis.gaps_identified
                    })

                    for fq in gap_analysis.follow_up_queries:
                        q_model = SearchQuery(
                            research_id=research.id,
                            query=fq,
                            results_count=0,
                            is_follow_up=True
                        )
                        self.db.add(q_model)
                    await self.db.commit()

                    additional_sources = await self.researcher.execute_searches(
                        gap_analysis.follow_up_queries,
                        research_domain=domain_str,
                        max_per_query=2
                    )
                    research.search_calls += len(gap_analysis.follow_up_queries)
                    research.fetch_calls += len(additional_sources)

                    for asrc in additional_sources:
                        source_model = Source(
                            research_id=research.id,
                            url=asrc.url,
                            title=asrc.title,
                            domain=asrc.domain,
                            published_at=asrc.published_at,
                            retrieved_at=asrc.retrieved_at,
                            content=asrc.content,
                            source_type=asrc.source_type,
                            relevance_score=asrc.relevance_score,
                            evaluation_factors=asrc.evaluation_factors,
                            evaluation_notes=asrc.evaluation_notes,
                            embedding=asrc.embedding
                        )
                        self.db.add(source_model)
                        collected_sources.append(asrc)
                    await self.db.commit()
                    await self._emit_event(research_id, "follow_up.completed", "researcher", {
                        "additional_sources_count": len(additional_sources)
                    })

            # 6. Synthesizing phase
            research.status = ResearchStatus.SYNTHESIZING
            await self.db.commit()
            await self._emit_event(research_id, "synthesizer.started", "synthesizer", {"domain": domain_str})

            report_data = await self.synthesizer.generate_report(research.question, collected_sources, domain=domain_str)
            research.llm_calls += 1

            report_model = Report(
                research_id=research.id,
                title=report_data.title,
                markdown_content=report_data.markdown_content,
                executive_summary=report_data.executive_summary,
                limitations=report_data.limitations,
                citations=report_data.citations
            )
            self.db.add(report_model)

            # 7. Completion
            research.status = ResearchStatus.COMPLETED
            research.completed_at = datetime.now(timezone.utc)
            research.runtime_seconds = round(time.time() - start_time, 2)
            await self.db.commit()
            await self._emit_event(research_id, "research.completed", "orchestrator", {"runtime": research.runtime_seconds})

            return research

        except Exception as e:
            research.status = ResearchStatus.FAILED
            research.error_message = str(e)
            research.runtime_seconds = round(time.time() - start_time, 2)
            await self.db.commit()
            await self._emit_event(research_id, "research.failed", "orchestrator", {"error": str(e)})
            raise
