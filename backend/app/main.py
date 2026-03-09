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
from app.api.cron import router as cron_router
from app.api.documents import router as documents_router
from app.api.gateway import router as gateway_router
from app.api.keys import router as keys_router
from app.api.logs import router as logs_router
from app.api.plugins import router as plugins_router
from app.api.settings import router as settings_router
from app.api.tts import router as tts_router
from app.api.usage import router as usage_router
from app.api.voice import router as voice_router
from app.api.webhooks import router as webhooks_router
from app.channels.discord import DiscordChannel
from app.channels.slack import SlackChannel
from app.channels.telegram import TelegramChannel
from app.channels.webhook import WebhookChannel
from app.channels.whatsapp import WhatsAppChannel
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
        tg_adapter = TelegramChannel(settings.telegram_bot_token, settings.telegram_webhook_url)
        channel_registry.register(tg_adapter)
        app.include_router(tg_adapter.router, prefix="/api/channels/telegram")
    if settings.feishu_app_id and settings.feishu_app_secret:
        fs_adapter = FeishuChannel(settings.feishu_app_id, settings.feishu_app_secret)
        channel_registry.register(fs_adapter)
        app.include_router(fs_adapter.router, prefix="/api/channels/feishu")
    if settings.discord_bot_token:
        channel_registry.register(DiscordChannel(settings.discord_bot_token))
    if settings.slack_bot_token and settings.slack_app_token:
        channel_registry.register(
            SlackChannel(settings.slack_bot_token, settings.slack_app_token)
        )
    if settings.whatsapp_account_sid and settings.whatsapp_auth_token:
        ws_adapter = WhatsAppChannel(
            settings.whatsapp_account_sid,
            settings.whatsapp_auth_token,
            settings.whatsapp_from_number,
        )
        channel_registry.register(ws_adapter)
        app.include_router(ws_adapter.router, prefix="/api/channels/whatsapp")

    # Always register generic webhook for extensibility
    wh_adapter = WebhookChannel()
    channel_registry.register(wh_adapter)
    app.include_router(wh_adapter.router, prefix="/api/channels/webhook")

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
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(cron_router)
app.include_router(documents_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(plugins_router)
app.include_router(gateway_router)
app.include_router(tts_router)
app.include_router(voice_router)
app.include_router(usage_router)
app.include_router(webhooks_router)
app.include_router(keys_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
