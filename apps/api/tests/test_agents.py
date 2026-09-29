import json
from datetime import UTC, datetime
from typing import Optional

import pytest

from app.agents.base import AgentOutputError, MeteredLLM, generate_structured
from app.agents.evidence import EvidenceSource
from app.agents.gap_analyzer.agent import GapAnalyzerAgent
from app.agents.planner.agent import PlannerAgent
from app.agents.researcher.agent import ResearcherAgent, classify_domain
from app.agents.synthesizer.agent import SynthesizerAgent, normalize_citations, strip_markdown
from app.agents.verifier.agent import SourceIndex, VerifierAgent, coerce_confidence, coerce_status
from app.models.research import ClaimStatus
from app.providers.llm.base import LLMProvider, LLMResponse
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.base import SearchProvider, SearchResult
from app.providers.search.mock import MockSearchProvider
from app.services.fetcher import FetchError


class ScriptedLLM(LLMProvider):
    """Returns the given answers in order (and records the prompts)."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, *answers: str):
        self.answers = list(answers)
        self.prompts: list[str] = []

    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=2000, json_mode=False):
        self.prompts.append(prompt)
        return LLMResponse(content=self.answers.pop(0), tokens_used=10)


def _sources(n: int) -> list[EvidenceSource]:
    return [
        EvidenceSource(
            id=f"s{i}", url=f"https://site{i}.org/page", title=f"Source {i}", domain=f"site{i}.org", content=f"Content {i}"
        )
        for i in range(1, n + 1)
    ]


async def test_generate_structured_repairs_once_then_fails():
    llm = ScriptedLLM("not json", '{"ok": 1}')
    assert await generate_structured(llm, prompt="p", system_prompt="s", parse=lambda d: d["ok"]) == 1
    assert "could not be used" in llm.prompts[1]

    with pytest.raises(AgentOutputError):
        await generate_structured(ScriptedLLM("nope", "still nope"), prompt="p", system_prompt="s", parse=lambda d: d)


async def test_metered_llm_counts_calls_and_tokens():
    metered = MeteredLLM(ScriptedLLM("a", "b"))
    await metered.generate("x")
    await metered.generate("y")
    assert (metered.calls, metered.tokens) == (2, 20)


async def test_planner_normalizes_and_bounds_queries():
    answer = json.dumps(
        {
            "objective": "o",
            "sub_questions": "single",
            "search_queries": ["q1?", '"Q1"', "q2", "q3", "q4", "q5"],
            "research_scope": "s",
        }
    )
    plan = await PlannerAgent(ScriptedLLM(answer)).create_plan("What is X?", depth="quick")
    assert plan.search_queries == ["q1", "q2", "q3"]  # deduplicated, cleaned, capped for quick
    assert plan.sub_questions == ["single"]


async def test_planner_without_queries_is_an_error_and_fallback_searches_the_question():
    with pytest.raises(AgentOutputError):
        await PlannerAgent(ScriptedLLM('{"objective": "o"}', '{"objective": "o"}')).create_plan("What is X?")
    fallback = PlannerAgent.fallback_plan("What are the benefits of remote work for productivity?")
    assert fallback.search_queries[0] == "What are the benefits of remote work for productivity"
    assert "remote work productivity" in fallback.search_queries[1]


def test_verifier_status_and_confidence_coercion():
    assert coerce_status("Partially Supported") == ClaimStatus.PARTIALLY_SUPPORTED
    assert coerce_status("refuted") == ClaimStatus.CONTRADICTED
    assert coerce_status("???") == ClaimStatus.INSUFFICIENT_EVIDENCE
    assert coerce_confidence("85") == 0.85
    assert coerce_confidence(7) == 0.07
    assert coerce_confidence(1.7) == 1.0 and coerce_confidence("n/a") == 0.5


def test_source_index_resolves_numbers_and_urls_only_when_valid():
    index = SourceIndex(_sources(3))
    assert index.resolve(2) == "https://site2.org/page"
    assert index.resolve("[3]") == "https://site3.org/page"
    assert index.resolve("https://www.site1.org/page/") == "https://site1.org/page"
    assert index.resolve(9) is None and index.resolve("https://hallucinated.org") is None and index.resolve(True) is None


async def test_verifier_maps_sources_and_drops_hallucinations():
    answer = """{"claims": [
        {"claim_text": "A", "status": "supported", "confidence": 0.9, "supporting_sources": [1, 7],
         "contradicting_sources": [1, 2], "reasoning": "r"},
        {"claim_text": "B", "status": "supported", "confidence": 0.8, "supporting_sources": ["https://fake.org"]},
        {"status": "supported"}
    ], "contradictions": [{"topic": "T", "point_a": "x", "source_a": 1, "point_b": "y", "source_b": 99, "explanation": "e"}]}"""
    result = await VerifierAgent(ScriptedLLM(answer)).verify("Q?", _sources(2))
    a, b = result.claims
    assert a.supporting_sources == ["https://site1.org/page"]
    assert a.contradicting_sources == ["https://site2.org/page"]  # a source cannot both support and contradict
    assert b.status == ClaimStatus.INSUFFICIENT_EVIDENCE  # "supported" without any valid source is downgraded
    assert result.contradictions[0].source_b_url == ""


async def test_verifier_never_invents_claims():
    # The first version returned hard-coded claims about learning Python here.
    with pytest.raises(AgentOutputError):
        await VerifierAgent(ScriptedLLM("garbage", "more garbage")).verify("Q?", _sources(2))
    assert (await VerifierAgent(ScriptedLLM()).verify("Q?", [])).claims == []


async def test_gap_analyzer_filters_repeated_queries():
    answer = json.dumps(
        {
            "is_sufficient": False,
            "gaps_identified": ["g"],
            "follow_up_queries": ["Already run", "new query", "new query", "third", "fourth"],
        }
    )
    result = await GapAnalyzerAgent(ScriptedLLM(answer)).analyze_gaps("Q", [], previous_queries=["already run"], max_queries=2)
    assert result.follow_up_queries == ["new query", "third"]
    assert result.is_sufficient is False

    done = await GapAnalyzerAgent(ScriptedLLM('{"is_sufficient": true, "follow_up_queries": ["x"]}')).analyze_gaps("Q", [])
    assert done.is_sufficient and done.follow_up_queries == []


def test_citation_normalization():
    text, cited = normalize_citations("A [1, 2] B [2-4] C [9] D [3][3] `code [7]`\n```\n[8]\n```", source_count=5)
    assert text.startswith("A [1][2] B [2][3][4] C  D [3] ")
    assert "[7]" in text and "[8]" in text  # code is left untouched
    assert cited == {1, 2, 3, 4}


def test_strip_markdown_keeps_french_typography():
    assert strip_markdown("**Résumé** : c'est vrai [1]. Pourquoi ? [2][3]") == "Résumé : c'est vrai. Pourquoi ?"


def test_parse_report_extracts_title_summary_limitations_and_citations():
    raw = """```markdown
# Rapport : énergie

## Résumé exécutif
Premier paragraphe du résumé [1].

Second paragraphe.

## Principaux résultats
### A
Texte [2] et [7].

## Limites
- Peu de sources [1]
- Données anciennes
```"""
    report = SynthesizerAgent.parse_report(raw, "Question ?", _sources(3))
    assert report.title == "Rapport : énergie"
    assert report.executive_summary == "Premier paragraphe du résumé."
    assert report.limitations == ["Peu de sources", "Données anciennes"]
    assert "[7]" not in report.markdown_content
    assert [c["cited"] for c in report.citations] == [True, True, False]
    assert report.citations[0]["source_id"] == "s1"


def test_parse_report_without_title_uses_question():
    report = SynthesizerAgent.parse_report("Just text about things.", "Why is the sky blue?", _sources(1))
    assert report.title == "Why is the sky blue?"
    assert report.markdown_content.startswith("# Why is the sky blue?")


def test_domain_classification():
    assert classify_domain("arxiv.org", "academic")[0] == "preprint"
    assert classify_domain("www.nature.com", "general") == ("peer_reviewed_paper", 0.95)
    assert classify_domain("docs.python.org", "technical") == ("technical_documentation", 0.95)
    assert classify_domain("unknown-blog.net", "general", hint="encyclopedia")[0] == "encyclopedia"


class _FakeFetcher:
    def __init__(self, pages: dict[str, Optional[str]]):
        self.pages = pages

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch(self, url):
        from app.services.fetcher import FetchedPage

        html = self.pages.get(url)
        if html is None:
            raise FetchError("HTTP 403")
        return FetchedPage(url=url, final_url=url, content_type="text/html", text=html)


class _ListSearch(SearchProvider):
    name = "list"

    def __init__(self, results):
        self.results = results

    async def search(self, query, max_results=5, domain="general"):
        return self.results[:max_results]


async def test_researcher_fetches_falls_back_to_snippets_and_skips_empty_results():
    paragraphs = "".join(f"<p>Useful fact number {i} about topic X, with supporting details.</p>" for i in range(12))
    article = f"<html><head><title>Good page</title></head><body><article>{paragraphs}</article></body></html>"
    results = [
        SearchResult(title="Good", url="https://good.org/a", snippet="s"),
        SearchResult(title="Blocked", url="https://blocked.org/b", snippet="A long enough snippet describing topic X in detail."),
        SearchResult(title="Empty", url="https://empty.org/c", snippet="tiny"),
        SearchResult(title="Dup", url="https://www.good.org/a/", snippet="duplicate"),
        SearchResult(title="Known", url="https://known.org/", snippet="already collected"),
    ]
    researcher = ResearcherAgent(_ListSearch(results), fetcher_factory=lambda: _FakeFetcher({"https://good.org/a": article}))
    outcome = await researcher.collect(
        ["topic X"], question="What about topic X?", max_per_query=10, known_urls={"https://known.org"}, origin="follow_up"
    )
    by_url = {s.url: s for s in outcome.sources}
    assert set(by_url) == {"https://good.org/a", "https://blocked.org/b"}
    assert by_url["https://good.org/a"].fetch_status == "ok" and "Useful fact number 3" in by_url["https://good.org/a"].content
    assert by_url["https://blocked.org/b"].fetch_status == "snippet"
    assert "Synthetic" not in by_url["https://blocked.org/b"].content  # no fabricated content
    assert by_url["https://good.org/a"].relevance_score > by_url["https://blocked.org/b"].relevance_score
    assert all(s.origin == "follow_up" and s.origin_query == "topic X" for s in outcome.sources)
    assert (outcome.fetch_calls, outcome.failed_fetches) == (3, 2)


async def test_full_mock_agent_chain_is_question_specific():
    llm = MockLLMProvider()
    plan = await PlannerAgent(llm).create_plan("How does solar geoengineering affect rainfall?", depth="standard")
    assert all("solar geoengineering" in q for q in plan.search_queries)

    researcher = ResearcherAgent(MockSearchProvider())
    outcome = await researcher.collect(plan.search_queries, question="How does solar geoengineering affect rainfall?")
    assert outcome.fetch_calls == 0  # mock results carry their content: no network
    evidence = [
        EvidenceSource(
            id=str(i), **s.model_dump(include={"url", "title", "domain", "source_type", "content", "relevance_score", "origin"})
        )
        for i, s in enumerate(outcome.sources)
    ]
    verification = await VerifierAgent(llm).verify("How does solar geoengineering affect rainfall?", evidence)
    assert any("solar geoengineering" in c.claim_text for c in verification.claims)
    report = await SynthesizerAgent(llm).generate_report(
        "How does solar geoengineering affect rainfall?",
        evidence,
        claims=verification.claims,
        contradictions=verification.contradictions,
    )
    assert report.title.lower().startswith("solar geoengineering")
    assert any(c["cited"] for c in report.citations)
    assert datetime.now(UTC)  # smoke: nothing above touched the network
