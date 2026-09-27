from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    db_status = "unknown"
    redis_status = "unknown"

    # Database Check
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Redis Check
    try:
        r = await get_redis()
        pong = await r.ping()
        redis_status = "healthy" if pong else "unhealthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "app_name": settings.APP_NAME,
        "mock_mode": settings.MOCK_MODE,
        "database": db_status,
        "redis": redis_status,
        "llm_provider": settings.LLM_PROVIDER,
        "search_provider": settings.SEARCH_PROVIDER
    }
