from app.core.config import settings
from app.providers.llm.anthropic import AnthropicProvider
from app.providers.llm.base import LLMError, LLMProvider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.llm.openai import OpenAICompatibleProvider

DEFAULT_MODELS = {
    "mock": "mock-1",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.1",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-5-5",
}

# name -> (base URL, settings attribute holding the key, key required)
_OPENAI_COMPATIBLE = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", True),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", True),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", True),
    "ollama": ("http://localhost:11434/v1", "OPENAI_API_KEY", False),
}


def configured_llm_name() -> str:
    return "mock" if settings.MOCK_MODE else (settings.LLM_PROVIDER.strip().lower() or "mock")


def configured_llm_model() -> str:
    name = configured_llm_name()
    return DEFAULT_MODELS["mock"] if name == "mock" else (settings.LLM_MODEL or DEFAULT_MODELS.get(name, ""))


def llm_key_present() -> bool:
    name = configured_llm_name()
    if name in ("mock", "ollama"):
        return True
    attr = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(name) or _OPENAI_COMPATIBLE.get(
        name, ("", "", True)
    )[1]
    return bool(attr and getattr(settings, attr, ""))


def get_llm_provider() -> LLMProvider:
    name = configured_llm_name()
    model = configured_llm_model()
    timeout = settings.LLM_TIMEOUT_SECONDS
    if name == "mock":
        return MockLLMProvider()
    if name in _OPENAI_COMPATIBLE:
        base_url, key_attr, require_key = _OPENAI_COMPATIBLE[name]
        extra_headers = {"X-Title": "AI Research Agent"} if name == "openrouter" else None
        return OpenAICompatibleProvider(
            name=name,
            base_url=settings.LLM_BASE_URL or base_url,
            api_key=getattr(settings, key_attr),
            api_key_env=key_attr,
            require_key=require_key,
            model=model,
            timeout=timeout,
            extra_headers=extra_headers,
        )
    if name == "gemini":
        return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=model, timeout=timeout)
    if name == "anthropic":
        return AnthropicProvider(
            api_key=settings.ANTHROPIC_API_KEY, model=model, timeout=timeout, effort=settings.ANTHROPIC_EFFORT
        )
    raise LLMError(f"Unknown LLM_PROVIDER '{name}' (expected one of: {', '.join(DEFAULT_MODELS)})")
