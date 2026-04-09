import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.channels.loader import load_and_register_channels
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
from app.gateway.channel_registry import ChannelRegistry
from app.infra.minio import get_minio_client
from app.infra.qdrant import close_qdrant_client, get_qdrant_client
from app.plugins import plugin_registry
from app.plugins.loader import (
    activate_all_plugins,
    deactivate_all_plugins,
    load_all_plugins,
)
from app.scheduler.runner import start_scheduler, stop_scheduler
from app.tools.mcp_client import mcp_connection_pool
from app.tools.subagent_tool import set_graph_factory as _set_subagent_graph_factory

configure_logging()
logger = structlog.get_logger(__name__)


class _ConcreteGraphFactory:
    async def create(self, messages: object, config: object) -> object:
        from app.agent.graph import create_graph

        return create_graph(**(config if isinstance(config, dict) else {}))


_set_subagent_graph_factory(_ConcreteGraphFactory())  # type: ignore[arg-type]
channel_registry = ChannelRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Initializing infrastructure and plugins...")
    await get_qdrant_client()
    get_minio_client()

    if not os.getenv("CI_E2E"):
        # 基础设施连接验证逻辑 (略，保持原有逻辑)
        pass

    # 动态加载渠道
    await load_and_register_channels(app, channel_registry)
    await channel_registry.start_all()

    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)
    await start_scheduler()

    # 指标轮询逻辑 (略)
    yield
    await stop_scheduler()
    await channel_registry.stop_all()
    await deactivate_all_plugins(plugin_registry)
    await mcp_connection_pool.close_all()
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

# 使用统一的 api_router
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
