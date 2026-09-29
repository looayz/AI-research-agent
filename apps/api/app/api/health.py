import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.cache import get_cache
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.providers.llm.factory import configured_llm_model, configured_llm_name, llm_key_present
from app.providers.search.factory import configured_search_names

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


def _search_configured(names: list[str]) -> bool:
    requirements = {"tavily": settings.TAVILY_API_KEY, "searxng": settings.SEARXNG_BASE_URL}
    return all(bool(requirements[name]) for name in names if name in requirements)


@router.get("/health")
async def health_check():
    db_ok = True
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - reported as unhealthy, details only in the logs
        logger.exception("Database health check failed")
        db_ok = False

    cache = get_cache()
    cache_ok = await cache.ping()
    llm_name = configured_llm_name()
    search_names = configured_search_names()

    body = {
        "status": "healthy" if db_ok and cache_ok else ("degraded" if db_ok else "unhealthy"),
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "mock_mode": settings.MOCK_MODE,
        "demo_mode": llm_name == "mock" or "mock" in search_names,
        "database": {"status": "healthy" if db_ok else "unhealthy", "backend": "sqlite" if settings.is_sqlite else "postgresql"},
        "cache": {"status": "healthy" if cache_ok else "unhealthy", "backend": cache.backend},
        "llm": {"provider": llm_name, "model": configured_llm_model(), "configured": llm_key_present()},
        "search": {"providers": search_names, "configured": _search_configured(search_names)},
        "limits": {
            "max_sources": settings.MAX_SOURCES,
            "max_search_queries": settings.MAX_SEARCH_QUERIES,
            "max_runtime_seconds": settings.MAX_RUNTIME_SECONDS,
        },
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)
