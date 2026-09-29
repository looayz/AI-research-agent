from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api — resolved from this file so behaviour does not depend on the CWD
# (start.sh runs from apps/api, start.bat and the npm scripts from the root).
API_DIR = Path(__file__).resolve().parents[2]
# Lowest priority first; real environment variables always win.
ENV_FILES = tuple(dict.fromkeys(str(p) for p in (API_DIR.parent.parent / ".env", API_DIR / ".env")))


class Settings(BaseSettings):
    APP_NAME: str = "AI Research Agent API"
    APP_VERSION: str = "0.3.0"
    APP_ENV: str = "development"
    # Echo every SQL statement. Very noisy, keep it off unless debugging queries.
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Forces the offline demo providers, whatever LLM_PROVIDER / SEARCH_PROVIDER
    # say. With the defaults below (both "mock") the app runs in demo mode anyway.
    MOCK_MODE: bool = False
    # Simulated latency of the demo providers, so the live pipeline is visible.
    MOCK_LATENCY_SECONDS: float = 0.8

    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database: falls back to a local async SQLite file for native execution.
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(API_DIR / 'research_agent.db').as_posix()}"

    # Optional. When set, search results and fetched pages are cached in Redis
    # (shared between workers); otherwise an in-process cache is used.
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 6 * 3600

    # LLM provider: mock | openai | groq | openrouter | ollama | gemini | anthropic
    LLM_PROVIDER: str = "mock"
    # Empty = provider default (see app/providers/llm/factory.py).
    LLM_MODEL: str = ""
    # Override the endpoint of OpenAI-compatible providers (LM Studio, vLLM, ...).
    LLM_BASE_URL: str = ""
    LLM_TIMEOUT_SECONDS: float = 300.0
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    # Claude only: low | medium | high | xhigh | max (empty = model default)
    ANTHROPIC_EFFORT: str = "medium"

    # Search provider: mock | tavily | searxng | duckduckgo | wikipedia | arxiv
    # Several providers can be combined with commas, e.g. "tavily,arxiv".
    SEARCH_PROVIDER: str = "mock"
    TAVILY_API_KEY: str = ""
    SEARXNG_BASE_URL: str = ""
    WIKIPEDIA_LANG: str = "en"
    SEARCH_TIMEOUT_SECONDS: float = 20.0

    # Page fetching
    FETCH_TIMEOUT_SECONDS: float = 12.0
    FETCH_MAX_BYTES: int = 3_000_000
    FETCH_USER_AGENT: str = "AIResearchAgent/0.3 (+https://github.com/looayz/AI-research-agent)"
    # Only for trusted local setups: lets the fetcher reach private networks.
    FETCH_ALLOW_PRIVATE_NETWORKS: bool = False
    MAX_CONCURRENT_FETCHES: int = 5

    # Semantic memory
    MEMORY_RECALL_ENABLED: bool = True
    MEMORY_RECALL_THRESHOLD: float = 0.35
    MEMORY_RECALL_LIMIT: int = 3

    # Limits
    MAX_SEARCH_QUERIES: int = 6
    MAX_SOURCES: int = 30
    MAX_FOLLOW_UP_SEARCHES: int = 3
    MAX_RUNTIME_SECONDS: int = 600

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
