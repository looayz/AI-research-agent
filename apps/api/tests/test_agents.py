import pytest
from app.providers.llm.mock import MockLLMProvider
from app.agents.planner.agent import PlannerAgent
from app.agents.researcher.agent import ResearcherAgent
from app.agents.verifier.agent import VerifierAgent
from app.agents.gap_analyzer.agent import GapAnalyzerAgent
from app.agents.synthesizer.agent import SynthesizerAgent
from app.providers.search.mock import MockSearchProvider
from app.models.research import ClaimStatus
from app.services.embedding import EmbeddingService


@pytest.mark.asyncio
async def test_planner_agent_creates_valid_plan_with_domain():
    llm = MockLLMProvider()
    planner = PlannerAgent(llm)
    plan = await planner.create_plan("Compare modern approaches to learning Python effectively", domain="academic")

    assert plan.objective != ""
    assert len(plan.sub_questions) >= 2
    assert len(plan.search_queries) >= 2


@pytest.mark.asyncio
async def test_researcher_agent_collects_sources_with_embeddings():
    search = MockSearchProvider()
    researcher = ResearcherAgent(search)
    sources = await researcher.execute_searches(
        ["best practices learning python"],
        research_domain="academic",
        max_per_query=2
    )

    assert len(sources) > 0
    assert sources[0].url.startswith("http")
    assert sources[0].title != ""
    assert sources[0].content != ""
    assert len(sources[0].embedding) == 128


def test_embedding_service_cosine_similarity():
    v1 = EmbeddingService.compute_embedding("python programming active learning")
    v2 = EmbeddingService.compute_embedding("python programming project based")
    v3 = EmbeddingService.compute_embedding("quantum mechanics astrophysics")

    sim_related = EmbeddingService.cosine_similarity(v1, v2)
    sim_unrelated = EmbeddingService.cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.4


@pytest.mark.asyncio
async def test_verifier_agent_extracts_claims_and_contradictions():
    llm = MockLLMProvider()
    search = MockSearchProvider()
    researcher = ResearcherAgent(search)
    verifier = VerifierAgent(llm)

    sources = await researcher.execute_searches(["learning python"], max_per_query=2)
    verification = await verifier.verify("Compare modern approaches to learning Python", sources)

    assert len(verification.claims) > 0
    assert verification.claims[0].status in [
        ClaimStatus.SUPPORTED,
        ClaimStatus.PARTIALLY_SUPPORTED,
        ClaimStatus.CONTRADICTED,
        ClaimStatus.INSUFFICIENT_EVIDENCE
    ]
    assert len(verification.contradictions) > 0
    assert verification.contradictions[0].explanation != ""


@pytest.mark.asyncio
async def test_gap_analyzer_identifies_follow_ups():
    llm = MockLLMProvider()
    gap_analyzer = GapAnalyzerAgent(llm)
    search = MockSearchProvider()
    researcher = ResearcherAgent(search)
    verifier = VerifierAgent(llm)

    sources = await researcher.execute_searches(["learning python"], max_per_query=2)
    verification = await verifier.verify("Compare modern approaches to learning Python", sources)

    analysis = await gap_analyzer.analyze_gaps("Compare modern approaches to learning Python", verification.claims, current_depth="deep")
    assert analysis.is_sufficient is False
    assert len(analysis.follow_up_queries) > 0


@pytest.mark.asyncio
async def test_synthesizer_agent_generates_report_with_domain():
    llm = MockLLMProvider()
    search = MockSearchProvider()
    researcher = ResearcherAgent(search)
    synthesizer = SynthesizerAgent(llm)

    sources = await researcher.execute_searches(["learning python"], max_per_query=2)
    report = await synthesizer.generate_report("Compare modern approaches to learning Python", sources, domain="technical")

    assert "# Research Report" in report.markdown_content
    assert len(report.citations) == len(sources)
    assert report.citations[0]["source_type"] != ""
