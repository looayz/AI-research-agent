from app.core.config import settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.llm.openai import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    if settings.MOCK_MODE or settings.LLM_PROVIDER == "mock":
        return MockLLMProvider()
    elif settings.LLM_PROVIDER == "openai":
        return OpenAIProvider()
    return MockLLMProvider()
