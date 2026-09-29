import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.memory import router as memory_router
from app.api.research import router as research_router
from app.core.cache import close_cache
from app.core.config import settings
from app.core.database import engine, init_db
from app.services.orchestrator import recover_interrupted_researches
from app.services.tasks import task_manager

logging.basicConfig(level=settings.LOG_LEVEL.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    interrupted = await recover_interrupted_researches()
    if interrupted:
        logger.warning("Marked %d interrupted research(es) as failed", interrupted)
    yield
    await task_manager.shutdown()
    await close_cache()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)  # /health, used by container health checks
app.include_router(health_router, prefix=settings.API_PREFIX, include_in_schema=False)  # /api/health for the web app
app.include_router(research_router, prefix=settings.API_PREFIX)
app.include_router(memory_router, prefix=settings.API_PREFIX)
