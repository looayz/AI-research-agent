import json

import httpx
import pytest

from app.core.config import settings
from app.providers.llm.anthropic import AnthropicProvider
from app.providers.llm.base import LLMError
from app.providers.llm.factory import get_llm_provider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.openai import OpenAICompatibleProvider
from app.providers.search.base import SearchError, SearchProvider, SearchResult
from app.providers.search.factory import CompositeSearchProvider, get_search_provider
from app.providers.search.mock import MockSearchProvider
from app.providers.search.web import (
    ArxivSearchProvider,
    DuckDuckGoSearchProvider,
    SearxngSearchProvider,
    TavilySearchProvider,
    WikipediaSearchProvider,
)

# ------------------------------------------------------------------ LLM


def _openai(handler) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        name="openai", base_url="https://api.test/v1", model="gpt-test", api_key="sk-test", transport=httpx.MockTransport(handler)
    )


async def test_openai_compatible_request_and_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {"total_tokens": 42}})

    response = await _openai(handler).generate("hi", system_prompt="sys", json_mode=True, max_tokens=100)
    assert response.content == '{"ok": true}' and response.tokens_used == 42
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert seen["body"]["response_format"] == {"type": "json_object"}


async def test_openai_compatible_drops_unsupported_parameters():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "max_tokens" in body:
            return httpx.Response(
                400, json={"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}}
            )
        if "temperature" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature' does not support 0.2"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}]})

    response = await _openai(handler).generate("hi")
    assert response.content == "done"
    assert "max_completion_tokens" in bodies[-1] and "temperature" not in bodies[-1]


async def test_openai_errors_are_clean():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Incorrect API key provided"}})

    with pytest.raises(LLMError, match="HTTP 401 - Incorrect API key"):
        await _openai(handler).generate("hi")

    provider = OpenAICompatibleProvider(name="openai", base_url="https://x", model="m", api_key="")
    with pytest.raises(LLMError, match="missing API key"):
        await provider.generate("hi")


async def test_gemini_provider_parses_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "g-key"
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "sys"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": '{"a": 1}'}]}}],
                "usageMetadata": {"totalTokenCount": 17},
            },
        )

    provider = GeminiProvider(api_key="g-key", model="gemini-test", transport=httpx.MockTransport(handler))
    response = await provider.generate("hi", system_prompt="sys", json_mode=True)
    assert response.content == '{"a": 1}' and response.tokens_used == 17


def _anthropic(handler, model: str) -> AnthropicProvider:
    import anthropic
    import httpx2

    client = anthropic.AsyncAnthropic(
        api_key="a-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), max_retries=0
    )
    return AnthropicProvider(api_key="a-key", model=model, effort="medium", client=client)


def _message(text: str, stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


async def test_anthropic_current_model_request_shape():
    import httpx2

    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=_message('{"ok": true}'))

    response = await _anthropic(handler, "claude-opus-5-5").generate("hi", system_prompt="sys", temperature=0.1, max_tokens=500)
    assert response.content == '{"ok": true}' and response.tokens_used == 15
    body = seen["body"]
    assert "temperature" not in body  # rejected by current models
    assert body["max_tokens"] >= 16000  # thinking tokens count against it
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["system"] == "sys"


async def test_anthropic_older_model_request_and_refusal():
    import httpx2

    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=_message("", stop_reason="refusal", model="claude-haiku-4-5"))

    with pytest.raises(LLMError, match="declined"):
        await _anthropic(handler, "claude-haiku-4-5").generate("hi", temperature=0.3)
    # No sampling parameter, no effort (unsupported on Haiku 4.5), no fallback.
    assert "temperature" not in bodies[0]
    assert "fallbacks" not in bodies[0] and "output_config" not in bodies[0]


def test_llm_factory(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "LLM_MODEL", "")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://api.groq.com/openai/v1" and provider.model == "llama-3.3-70b-versatile"

    monkeypatch.setattr(settings, "MOCK_MODE", True)
    assert get_llm_provider().name == "mock"

    monkeypatch.setattr(settings, "MOCK_MODE", False)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nope")
    with pytest.raises(LLMError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()


# --------------------------------------------------------------- search


def _mock(handler) -> dict:
    return {"transport": httpx.MockTransport(handler)}


async def test_tavily_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tvly-key"
        assert json.loads(request.content)["include_raw_content"] is True
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "A", "url": "https://a.org/1", "content": "snippet", "score": 0.9, "raw_content": "x" * 500},
                    {"title": "B", "url": "https://b.org/2", "content": "short", "score": 0.5, "raw_content": "tiny"},
                ]
            },
        )

    results = await TavilySearchProvider("tvly-key", **_mock(handler)).search("q", max_results=2)
    assert [r.url for r in results] == ["https://a.org/1", "https://b.org/2"]
    assert results[0].content == "x" * 500 and results[1].content is None
    with pytest.raises(SearchError, match="missing API key"):
        await TavilySearchProvider("").search("q")


async def test_searxng_provider_normalizes_scores():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["format"] == "json" and request.url.params["categories"] == "science"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://a.org", "title": "A", "content": "c", "score": 4.0},
                    {"url": "https://b.org", "title": "B", "content": "c", "score": 2.0},
                ]
            },
        )

    results = await SearxngSearchProvider("http://searx:8080", **_mock(handler)).search("q", domain="academic")
    assert [r.score for r in results] == [1.0, 0.5]


async def test_duckduckgo_html_provider():
    html = """
    <div class="result results_links">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.org%2Fpage&rut=x">Real page</a>
      <a class="result__snippet">A useful snippet</a></div>
    <div class="result result--ad"><a class="result__a" href="https://ads.example/">Ad</a></div>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    results = await DuckDuckGoSearchProvider(**_mock(handler)).search("q")
    assert [(r.url, r.title, r.snippet) for r in results] == [("https://real.org/page", "Real page", "A useful snippet")]


async def test_wikipedia_provider_returns_extracts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "fr.wikipedia.org"
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "title": "Second",
                            "index": 2,
                            "extract": "Second intro.",
                            "fullurl": "https://fr.wikipedia.org/wiki/Second",
                        },
                        {
                            "title": "First",
                            "index": 1,
                            "extract": "First intro.",
                            "fullurl": "https://fr.wikipedia.org/wiki/First",
                            "revisions": [{"timestamp": "2026-01-02T00:00:00Z"}],
                        },
                        {"title": "Empty", "index": 3, "extract": ""},
                    ]
                }
            },
        )

    results = await WikipediaSearchProvider(lang="fr", **_mock(handler)).search("q")
    assert [r.title for r in results] == ["First - Wikipedia", "Second - Wikipedia"]
    assert results[0].content == "First intro." and results[0].published_date == "2026-01-02"
    assert results[0].source_type == "encyclopedia"


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <published>2024-01-01T00:00:00Z</published>
    <title>  Lattice-based   schemes </title>
    <summary>We study lattices.</summary>
    <author><name>Alice</name></author><author><name>Bob</name></author>
  </entry>
</feed>"""


async def test_arxiv_provider_parses_atom(monkeypatch):
    monkeypatch.setattr(ArxivSearchProvider, "_last_call", 0.0)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "all:lattice" in request.url.params["search_query"]
        return httpx.Response(200, text=ATOM)

    results = await ArxivSearchProvider(**_mock(handler)).search("lattice cryptography")
    assert results[0].url == "https://arxiv.org/abs/2401.00001v1"
    assert results[0].title == "Lattice-based schemes"
    assert "Alice, Bob" in results[0].content and results[0].source_type == "preprint"


class _StaticProvider(SearchProvider):
    def __init__(self, name, urls=None, error=None):
        self.name, self.urls, self.error = name, urls or [], error

    async def search(self, query, max_results=5, domain="general"):
        if self.error:
            raise SearchError(self.error)
        return [SearchResult(title=u, url=u, provider=self.name) for u in self.urls[:max_results]]


async def test_composite_interleaves_dedupes_and_tolerates_failures():
    composite = CompositeSearchProvider(
        [
            _StaticProvider("a", ["https://1.org", "https://2.org", "https://3.org"]),
            _StaticProvider("b", ["https://www.1.org/", "https://4.org"]),
            _StaticProvider("c", error="boom"),
        ]
    )
    results = await composite.search("q", max_results=4)
    assert [r.url for r in results] == ["https://1.org", "https://2.org", "https://4.org", "https://3.org"]

    with pytest.raises(SearchError, match="boom"):
        await CompositeSearchProvider([_StaticProvider("c", error="boom")]).search("q")


async def test_mock_search_is_offline_and_topic_aware():
    results = await MockSearchProvider().search("post-quantum cryptography overview", max_results=5, domain="technical")
    assert len(results) == 3
    assert all(r.url.split("/")[2].endswith(".example") for r in results)
    assert all("post-quantum cryptography" in r.content.lower() for r in results)


def test_search_factory(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "wikipedia, arxiv")
    provider = get_search_provider()
    assert provider.name == "wikipedia+arxiv"
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "bing")
    with pytest.raises(SearchError, match="Unknown SEARCH_PROVIDER"):
        get_search_provider()
