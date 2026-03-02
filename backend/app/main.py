import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.canvas import router as canvas_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.gateway import router as gateway_router
from app.api.logs import router as logs_router
from app.api.plugins import router as plugins_router
from app.api.settings import router as settings_router
from app.api.tts import router as tts_router
from app.api.usage import router as usage_router
from app.api.voice import router as voice_router
from app.api.webhooks import router as webhooks_router
from app.channels.slack import SlackChannel
from app.channels.telegram import TelegramChannel
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

configure_logging()
logger = structlog.get_logger(__name__)

# Global registry for messaging channels
channel_registry = ChannelRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle: verify infrastructure and initialize plugins."""
    logger.info("Checking infrastructure connections...")
    qdrant = await get_qdrant_client()
    await qdrant.get_collections()
    minio = get_minio_client()
    await asyncio.to_thread(minio.bucket_exists, settings.minio_bucket)
    logger.info("Infrastructure ready.")

    # Initialize and start messaging channels
    if settings.telegram_bot_token:
        channel_registry.register(TelegramChannel(settings.telegram_bot_token))
    if settings.slack_bot_token and settings.slack_app_token:
        channel_registry.register(
            SlackChannel(settings.slack_bot_token, settings.slack_app_token)
        )
    # TODO: Add DiscordChannel once implemented

    await channel_registry.start_all()

    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)
    await start_scheduler()
    yield
    await stop_scheduler()
    await channel_registry.stop_all()
    await deactivate_all_plugins(plugin_registry)
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
app.include_router(admin_router)
app.include_router(canvas_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(plugins_router)
app.include_router(gateway_router)
app.include_router(tts_router)
app.include_router(voice_router)
app.include_router(usage_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
