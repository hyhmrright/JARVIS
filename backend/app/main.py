import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
from app.infra.minio import get_minio_client
from app.infra.qdrant import get_qdrant_client
from app.scheduler.runner import start_scheduler, stop_scheduler

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI 生命周期管理：初始化 Qdrant、MinIO 客户端及调度器。"""
    logger.info("app_startup_begin")
    try:
        # 确保基础设施连接正常
        await get_qdrant_client()
        await asyncio.to_thread(get_minio_client)

        # 启动调度器
        await start_scheduler()

        yield
    finally:
        logger.info("app_shutdown_begin")
        await stop_scheduler()


app = FastAPI(
    title="JARVIS API",
    version="0.1.0",
    lifespan=lifespan,
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

# 监控配置
Instrumentator().instrument(app).expose(app)

# 注册路由
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
