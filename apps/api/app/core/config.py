from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Research Agent API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    MOCK_MODE: bool = True

    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database: fallback to local async sqlite file for standalone native execution
    DATABASE_URL: str = "sqlite+aiosqlite:///./research_agent.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI & Search Providers
    LLM_PROVIDER: str = "mock"
    SEARCH_PROVIDER: str = "mock"

    # Limits
    MAX_SEARCH_QUERIES: int = 20
    MAX_SOURCES: int = 30
    MAX_FOLLOW_UP_SEARCHES: int = 3
    MAX_AGENT_STEPS: int = 50
    MAX_RUNTIME_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
