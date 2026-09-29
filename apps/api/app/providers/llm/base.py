from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    model: str = ""


class LLMError(RuntimeError):
    """Raised when a provider is misconfigured or its API call fails."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion. ``json_mode`` asks for a single JSON object."""
