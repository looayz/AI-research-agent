from typing import Any, Optional

import httpx

from app.providers.http import error_detail, request_with_retries
from app.providers.llm.base import LLMError, LLMProvider, LLMResponse

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """Google Gemini through the Generative Language REST API."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        base_url: str = GEMINI_API_BASE,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMError("gemini: missing API key (set GEMINI_API_KEY)")

        generation_config: dict[str, Any] = {
            "temperature": temperature,
            # 2.5+ models spend part of the budget on thinking tokens.
            "maxOutputTokens": max(max_tokens, 8192),
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"{self.base_url}/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            try:
                resp = await request_with_retries(client, "POST", url, headers={"x-goog-api-key": self.api_key}, json=payload)
            except httpx.HTTPError as exc:
                raise LLMError(f"gemini: request failed ({type(exc).__name__})") from exc

        if resp.status_code >= 400:
            raise LLMError(f"gemini: HTTP {resp.status_code} - {error_detail(resp)}")

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback", {}).get("blockReason", "no candidates")
            raise LLMError(f"gemini: no completion ({feedback})")
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not content.strip():
            raise LLMError(f"gemini: empty completion (finishReason={candidates[0].get('finishReason', 'unknown')})")
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            content=content,
            tokens_used=int(usage.get("totalTokenCount", 0)),
            model=data.get("modelVersion", self.model),
        )
