import asyncio
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.research import Research, ResearchEvent, ResearchStatus
from app.providers.llm.base import LLMResponse
from app.providers.llm.mock import MockLLMProvider
from app.services.orchestrator import INTERRUPTED_MESSAGE, recover_interrupted_researches
from helpers import wait_for_research

QUESTION = "What are the trade-offs of post-quantum cryptography migration?"


async def _create(client, question=QUESTION, depth="standard", domain="technical") -> str:
    response = await client.post("/api/research", json={"question": question, "depth": depth, "domain": domain})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_health(client):
    for path in ("/health", "/api/health"):
        body = (await client.get(path)).json()
        assert body["status"] == "healthy"
        assert body["demo_mode"] is True
        assert body["llm"] == {"provider": "mock", "model": "mock-1", "configured": True}
        assert body["cache"]["backend"] == "memory"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "AI"},
        {"question": "     abc     "},
        {"question": "x" * 2001},
        {"question": "Valid question?", "depth": "extreme"},
    ],
)
async def test_invalid_payloads_are_rejected(client, payload):
    assert (await client.post("/api/research", json=payload)).status_code == 422


async def test_full_pipeline_standard(client):
    detail = await wait_for_research(client, await _create(client))
    assert detail["status"] == "completed", detail["error_message"]
    assert detail["plan"]["search_queries"]
    assert detail["claims"] and detail["contradictions"]
    assert detail["report"]["title"] and detail["report"]["executive_summary"]
    assert any(c["cited"] for c in detail["report"]["citations"])
    # Counters are real now (the first version always reported 0 tokens).
    assert detail["tokens_used"] > 0 and detail["llm_calls"] >= 4 and detail["search_calls"] >= 3
    # One gap-analysis round for "standard", with follow-up queries and sources.
    assert any(q["is_follow_up"] and q["iteration"] == 1 for q in detail["queries"])
    assert any(s["origin"] == "follow_up" for s in detail["sources"])
    # Events are ordered, and datetimes are explicit UTC.
    seqs = [e["seq"] for e in detail["events"]]
    assert seqs == sorted(seqs) == list(range(1, len(seqs) + 1))
    assert detail["events"][-1]["event_type"] == "research.completed"
    assert detail["created_at"].endswith("Z")
    # Sources expose an excerpt, not their full text.
    assert "content" not in detail["sources"][0] and detail["sources"][0]["excerpt"]
    # No duplicate URLs.
    urls = [s["url"] for s in detail["sources"]]
    assert len(urls) == len(set(urls))


async def test_depth_controls_the_gap_loop(client):
    quick = await wait_for_research(client, await _create(client, depth="quick"))
    deep = await wait_for_research(client, await _create(client, depth="deep"))
    assert not any(q["is_follow_up"] for q in quick["queries"])
    assert "gap_analyzer.started" not in [e["event_type"] for e in quick["events"]]
    rounds = {q["iteration"] for q in deep["queries"] if q["is_follow_up"]}
    assert rounds == {1, 2}
    assert len(deep["sources"]) > len(quick["sources"])


async def test_list_summary_search_and_pagination(client):
    first = await _create(client, question="Unique zebra migration patterns in Kenya?")
    await wait_for_research(client, first)
    body = (await client.get("/api/research", params={"q": "zebra", "limit": 5})).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == first and item["source_count"] > 0 and item["claim_count"] > 0
    assert item["report_title"] and item["executive_summary"]
    assert "sources" not in item  # lightweight list
    assert (await client.get("/api/research", params={"limit": 101})).status_code == 422
    completed = (await client.get("/api/research", params={"status": "completed", "limit": 1})).json()
    assert len(completed["items"]) == 1 and completed["total"] >= 1


async def test_rerun_creates_exactly_one_new_research(client):
    original = await _create(client, question="How do honeybees navigate?", depth="quick")
    await wait_for_research(client, original)
    before = (await client.get("/api/research", params={"q": "honeybees"})).json()["total"]
    rerun = await client.post(f"/api/research/{original}/rerun")
    assert rerun.status_code == 201 and rerun.json()["id"] != original
    await wait_for_research(client, rerun.json()["id"])
    after = (await client.get("/api/research", params={"q": "honeybees"})).json()["total"]
    assert after == before + 1


async def test_exclude_source_and_resynthesize(client):
    research_id = await _create(client, depth="quick")
    detail = await wait_for_research(client, research_id)
    cited = next(c for c in detail["report"]["citations"] if c["cited"])

    excluded = await client.post(f"/api/research/{research_id}/sources/{cited['source_id']}/exclude")
    assert excluded.status_code == 200 and excluded.json()["is_excluded"] is True

    response = await client.post(f"/api/research/{research_id}/resynthesize")
    assert response.status_code == 202
    assert (await client.post(f"/api/research/{research_id}/resynthesize")).status_code == 409  # already running
    updated = await wait_for_research(client, research_id)
    assert updated["status"] == "completed"
    assert cited["url"] not in [c["url"] for c in updated["report"]["citations"]]
    assert [e["event_type"] for e in updated["events"]].count("research.completed") == 2
    assert updated["llm_calls"] > detail["llm_calls"]  # usage accumulates

    included = await client.post(f"/api/research/{research_id}/sources/{cited['source_id']}/include")
    assert included.json()["is_excluded"] is False


async def test_resynthesize_needs_at_least_one_source(client):
    research_id = await _create(client, depth="quick")
    detail = await wait_for_research(client, research_id)
    for source in detail["sources"]:
        await client.post(f"/api/research/{research_id}/sources/{source['id']}/exclude")
    assert (await client.post(f"/api/research/{research_id}/resynthesize")).status_code == 400


async def test_source_detail_returns_full_content(client):
    research_id = await _create(client, depth="quick")
    detail = await wait_for_research(client, research_id)
    source_id = detail["sources"][0]["id"]
    full = (await client.get(f"/api/research/{research_id}/sources/{source_id}")).json()
    assert len(full["content"]) == full["content_length"] > 0
    assert (await client.get(f"/api/research/{research_id}/sources/nope")).status_code == 404


@pytest.fixture
def slow_llm(monkeypatch):
    original = MockLLMProvider.generate

    async def slow(self, *args, **kwargs):
        await asyncio.sleep(0.3)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(MockLLMProvider, "generate", slow)


async def test_cancel_stops_a_running_research(client, slow_llm):
    research_id = await _create(client, depth="deep")
    await asyncio.sleep(0.4)
    response = await client.post(f"/api/research/{research_id}/cancel")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    detail = await wait_for_research(client, research_id)
    assert detail["status"] == "cancelled"
    await asyncio.sleep(0.8)  # the pipeline must not resurrect the research
    detail = (await client.get(f"/api/research/{research_id}")).json()
    assert detail["status"] == "cancelled" and detail["report"] is None
    assert detail["events"][-1]["event_type"] == "research.cancelled"
    assert (await client.post(f"/api/research/{research_id}/cancel")).status_code == 409


async def test_delete_running_research(client, slow_llm):
    research_id = await _create(client, depth="deep")
    await asyncio.sleep(0.2)
    assert (await client.delete(f"/api/research/{research_id}")).status_code == 204
    assert (await client.get(f"/api/research/{research_id}")).status_code == 404


def _parse_sse(text: str) -> list[dict]:
    messages = []
    for block in text.strip().split("\n\n"):
        fields: dict = {}
        for line in block.splitlines():
            if line.startswith(":") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if "data" in fields:
            messages.append(fields)
    return messages


async def test_event_stream_replays_and_resumes(client):
    research_id = await _create(client, depth="quick")
    stream = await client.get(f"/api/research/{research_id}/events")
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "no-transform" in stream.headers["cache-control"]
    messages = _parse_sse(stream.text)
    events = [m for m in messages if m.get("event") != "end"]
    assert messages[-1]["event"] == "end" and json.loads(messages[-1]["data"])["status"] == "completed"
    assert [int(m["id"]) for m in events] == list(range(1, len(events) + 1))
    assert json.loads(events[-1]["data"])["event_type"] == "research.completed"

    resumed = _parse_sse((await client.get(f"/api/research/{research_id}/events", headers={"Last-Event-ID": "3"})).text)
    assert int(resumed[0]["id"]) == 4
    assert (await client.get("/api/research/unknown/events")).status_code == 404


async def test_export_markdown_and_json(client):
    research_id = await _create(client, depth="quick")
    await wait_for_research(client, research_id)
    md = await client.get(f"/api/research/{research_id}/export", params={"format": "md"})
    assert md.headers["content-type"].startswith("text/markdown")
    assert 'attachment; filename="' in md.headers["content-disposition"]
    assert "## Sources" in md.text and md.text.startswith("# ")
    exported = (await client.get(f"/api/research/{research_id}/export", params={"format": "json"})).json()
    assert exported["id"] == research_id and exported["report"]
    assert (await client.get(f"/api/research/{research_id}/export", params={"format": "pdf"})).status_code == 422


async def test_semantic_memory_recall_and_search(client):
    first = await _create(client, question="How do octopuses camouflage in coral reefs?", depth="quick")
    await wait_for_research(client, first)
    second = await wait_for_research(
        client, await _create(client, question="How do octopuses camouflage in coral reefs?", depth="quick")
    )
    recalled = [s for s in second["sources"] if s["origin"] == "memory"]
    assert recalled and all(not s["title"].startswith("[Reused Memory]") for s in recalled)
    assert all(s["evaluation_factors"]["memory_from_research"] == first for s in recalled)

    hits = (await client.post("/api/memory/search", json={"query": "octopuses camouflage coral reefs", "limit": 20})).json()
    urls = [h["source"]["url"] for h in hits]
    assert hits and len(urls) == len(set(urls))  # de-duplicated across investigations
    assert hits[0]["research_question"].startswith("How do octopuses")
    assert (await client.post("/api/memory/search", json={"query": "x", "limit": 500})).status_code == 422


async def test_missing_api_key_fails_with_a_clear_message(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    detail = await wait_for_research(client, await _create(client, depth="quick"))
    assert detail["status"] == "failed"
    assert detail["error_message"] == "openai: missing API key (set OPENAI_API_KEY)"
    assert detail["events"][-1]["event_type"] == "research.failed"


async def test_unusable_verifier_output_degrades_gracefully(client, monkeypatch):
    original = MockLLMProvider.generate

    async def broken_verifier(self, prompt, system_prompt=None, **kwargs):
        if "Evidence Verifier" in (system_prompt or ""):
            return LLMResponse(content="I cannot produce JSON today.", tokens_used=5)
        return await original(self, prompt, system_prompt=system_prompt, **kwargs)

    monkeypatch.setattr(MockLLMProvider, "generate", broken_verifier)
    detail = await wait_for_research(client, await _create(client, depth="quick"))
    assert detail["status"] == "completed"
    assert detail["claims"] == []  # nothing invented
    warnings = [e for e in detail["events"] if e["event_type"] == "warning"]
    assert warnings and "Verifier output was unusable" in warnings[0]["data"]["message"]


async def test_interrupted_researches_are_recovered():
    async with AsyncSessionLocal() as db:
        stuck = Research(question="Stuck forever?", status=ResearchStatus.SEARCHING)
        db.add(stuck)
        await db.commit()
        stuck_id = stuck.id
    assert await recover_interrupted_researches() >= 1
    async with AsyncSessionLocal() as db:
        research = await db.get(Research, stuck_id)
        assert research.status == ResearchStatus.FAILED and research.error_message == INTERRUPTED_MESSAGE
        last = (await db.execute(select(ResearchEvent).where(ResearchEvent.research_id == stuck_id))).scalars().one()
        assert last.event_type == "research.failed"
