from typing import Any, Optional

from app.providers.llm.base import LLMError, LLMProvider, LLMResponse

# Per-model request rules (Claude API). Sampling parameters (temperature...)
# are never sent: SDK 1.x dropped them and current models reject them.
# - these accept `output_config.effort`
_EFFORT = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-opus-4-5",
)
# - these support the server-side refusal fallback with "default" routing
_FALLBACK_DEFAULT = frozenset({"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"})


class AnthropicProvider(LLMProvider):
    """Claude through the official Anthropic SDK (imported lazily)."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 300.0,
        effort: str = "",
        client: Optional[Any] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.effort = effort
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - listed in requirements.txt
                raise LLMError("anthropic: SDK not installed (pip install anthropic)") from exc
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout, max_retries=2)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self.api_key and self._client is None:
            raise LLMError("anthropic: missing API key (set ANTHROPIC_API_KEY)")
        import anthropic

        client = self._get_client()
        # Thinking tokens count against max_tokens, so never lowball it.
        # JSON output is requested in the prompts: prefill is rejected by
        # current models and every agent parses/repairs JSON itself.
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max(max_tokens, 16000),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            params["system"] = system_prompt

        if self.effort and self.model.startswith(_EFFORT):
            params["output_config"] = {"effort": self.effort}

        try:
            if self.model in _FALLBACK_DEFAULT:
                # A declined request is retried server-side on the model
                # Anthropic recommends for that refusal category.
                response = await client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                response = await client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("anthropic: invalid API key") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"anthropic: unknown model '{self.model}'") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("anthropic: rate limited, try again later") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"anthropic: HTTP {exc.status_code} - {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("anthropic: connection error") from exc

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"anthropic: request declined by the model (category={category or 'unspecified'})")

        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise LLMError(f"anthropic: empty completion (stop_reason={response.stop_reason})")
        usage = response.usage
        tokens = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        return LLMResponse(content=text, tokens_used=tokens, model=response.model)
