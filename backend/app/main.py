import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.gateway import router as gateway_router
from app.api.logs import router as logs_router
from app.api.settings import router as settings_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
from app.infra.minio import get_minio_client
from app.infra.qdrant import close_qdrant_client, get_qdrant_client
from app.scheduler.runner import start_scheduler, stop_scheduler

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用启动/关闭生命周期：验证基础设施连接。"""
    logger.info("Checking infrastructure connections...")
    qdrant = await get_qdrant_client()
    await qdrant.get_collections()
    minio = get_minio_client()
    await asyncio.to_thread(minio.bucket_exists, settings.minio_bucket)
    logger.info("Infrastructure ready.")
    await start_scheduler()
    yield
    await stop_scheduler()
    await close_qdrant_client()
    logger.info("Shutting down.")


app = FastAPI(title="Jarvis API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(gateway_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
