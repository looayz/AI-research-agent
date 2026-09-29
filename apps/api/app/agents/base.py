from collections.abc import Callable
from typing import Any, Optional, TypeVar

from pydantic import ValidationError

from app.core.jsonutil import extract_json
from app.providers.llm.base import LLMProvider, LLMResponse

T = TypeVar("T")


class AgentOutputError(Exception):
    """The model answered, but not with usable structured output."""


class MeteredLLM(LLMProvider):
    """Counts calls and tokens so each research reports its real cost."""

    def __init__(self, inner: LLMProvider):
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.calls = 0
        self.tokens = 0

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        response = await self.inner.generate(
            prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
        )
        self.calls += 1
        self.tokens += response.tokens_used
        return response


async def generate_structured(
    llm: LLMProvider,
    *,
    prompt: str,
    system_prompt: str,
    parse: Callable[[Any], T],
    temperature: float = 0.1,
    max_tokens: int = 2000,
    retries: int = 1,
) -> T:
    """Ask for JSON, parse it, and give the model one chance to repair its answer."""
    last_error = ""
    for attempt in range(retries + 1):
        current = prompt
        if attempt:
            current = (
                f"{prompt}\n\nYour previous reply could not be used ({last_error}). "
                "Reply again with only the JSON object described in the instructions."
            )
        response = await llm.generate(
            current, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens, json_mode=True
        )
        try:
            return parse(extract_json(response.content))
        except (ValueError, ValidationError, TypeError, KeyError, AttributeError) as exc:
            last_error = str(exc).splitlines()[0][:200]
    raise AgentOutputError(last_error or "invalid structured output")
