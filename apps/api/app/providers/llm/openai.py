from typing import Any, Optional

import httpx

from app.providers.http import error_detail, request_with_retries
from app.providers.llm.base import LLMError, LLMProvider, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    """Chat Completions API: OpenAI, Groq, OpenRouter, Ollama, LM Studio, vLLM...

    Providers disagree on optional parameters (``response_format``,
    ``max_tokens`` vs ``max_completion_tokens``, ``temperature`` on reasoning
    models). When the API rejects one with a 400, the request is retried
    without it instead of failing the whole research.
    """

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        api_key_env: str = "OPENAI_API_KEY",
        require_key: bool = True,
        timeout: float = 120.0,
        extra_headers: Optional[dict[str, str]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.require_key = require_key
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._transport = transport

    @staticmethod
    def _adjust_payload(payload: dict[str, Any], message: str) -> bool:
        """Drop or rename the parameter an API complained about. True if changed."""
        msg = message.lower()
        if "response_format" in payload and ("response_format" in msg or "json_object" in msg or "json mode" in msg):
            payload.pop("response_format")
            return True
        if "max_tokens" in payload and "max_completion_tokens" in msg:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
            return True
        if "temperature" in payload and "temperature" in msg:
            payload.pop("temperature")
            return True
        return False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        if self.require_key and not self.api_key:
            raise LLMError(f"{self.name}: missing API key (set {self.api_key_env})")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {**self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            for _ in range(4):
                try:
                    resp = await request_with_retries(
                        client, "POST", f"{self.base_url}/chat/completions", headers=headers, json=payload
                    )
                except httpx.HTTPError as exc:
                    raise LLMError(f"{self.name}: request failed ({type(exc).__name__})") from exc
                if resp.status_code == 400 and self._adjust_payload(payload, error_detail(resp)):
                    continue
                break

        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} - {error_detail(resp)}")

        data = resp.json()
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.name}: unexpected response shape") from exc
        if not content.strip():
            reason = choice.get("finish_reason", "unknown")
            raise LLMError(f"{self.name}: empty completion (finish_reason={reason})")
        usage = data.get("usage") or {}
        tokens = usage.get("total_tokens") or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
        return LLMResponse(content=content, tokens_used=int(tokens or 0), model=data.get("model", self.model))


# Backwards compatible name used by earlier versions.
OpenAIProvider = OpenAICompatibleProvider
