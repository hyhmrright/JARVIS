import asyncio
import os
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
from app.api.chat_files import router as chat_files_router
from app.api.conversations import router as conversations_router
from app.api.cron import router as cron_router
from app.api.documents import router as documents_router
from app.api.export import router as export_router
from app.api.folders import router as folders_router
from app.api.gateway import router as gateway_router
from app.api.invitations import router as invitations_router
from app.api.keys import router as keys_router
from app.api.logs import router as logs_router
from app.api.memory import router as memory_router
from app.api.notifications import router as notifications_router
from app.api.organizations import router as organizations_router
from app.api.personas import router as personas_router
from app.api.plugins import router as plugins_router
from app.api.public import router as public_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.api.tts import router as tts_router
from app.api.usage import router as usage_router
from app.api.voice import router as voice_router
from app.api.webhooks import router as webhooks_router
from app.api.workflows import router as workflows_router
from app.api.workspaces import router as workspaces_router
from app.channels.discord import DiscordChannel
from app.channels.feishu import FeishuChannel
from app.channels.slack import SlackChannel
from app.channels.telegram import TelegramChannel
from app.channels.webhook import WebhookChannel
from app.channels.wechat import WeChatChannel
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
from app.tools.mcp_client import mcp_connection_pool
from app.tools.subagent_tool import set_graph_factory as _set_subagent_graph_factory

configure_logging()
logger = structlog.get_logger(__name__)


class _ConcreteGraphFactory:
    """Satisfies ``AgentGraphFactory`` protocol for subagent_tool."""

    async def create(self, messages: object, config: object) -> object:
        from app.agent.graph import create_graph

        return create_graph(**(config if isinstance(config, dict) else {}))


_set_subagent_graph_factory(_ConcreteGraphFactory())  # type: ignore[arg-type]

# Global registry for messaging channels
channel_registry = ChannelRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: C901
    """Startup/shutdown lifecycle: verify infrastructure and initialize plugins."""
    logger.info("Checking infrastructure connections...")
    qdrant = await get_qdrant_client()
    minio = get_minio_client()

    # Initialize infrastructure with retries and timeouts
    if not os.getenv("CI_E2E"):
        # Initialize infrastructure with retries and timeouts
        max_retries = 5
        retry_delay = 2
        step_timeout = 5.0

        # Check Qdrant
        for i in range(max_retries):
            try:
                await asyncio.wait_for(qdrant.get_collections(), timeout=step_timeout)
                logger.info("Qdrant connection verified.")
                break
            except Exception as e:
                if i == max_retries - 1:
                    logger.error("qdrant_connection_failed_after_retries", error=str(e))
                else:
                    logger.warning(f"qdrant_not_ready_retrying_{i + 1}/{max_retries}")
                    await asyncio.sleep(retry_delay)

        # Check MinIO
        for i in range(max_retries):
            try:
                exists = await asyncio.wait_for(
                    asyncio.to_thread(minio.bucket_exists, settings.minio_bucket),
                    timeout=step_timeout,
                )
                if not exists:
                    await asyncio.to_thread(minio.make_bucket, settings.minio_bucket)
                logger.info("MinIO connection verified and bucket ensured.")
                break
            except Exception as e:
                if i == max_retries - 1:
                    logger.error("minio_connection_failed_after_retries", error=str(e))
                else:
                    logger.warning(f"minio_not_ready_retrying_{i + 1}/{max_retries}")
                    await asyncio.sleep(retry_delay)

    else:
        logger.info("CI_E2E mode: skipping infrastructure verification")
    logger.info("Infrastructure ready.")

    # Initialize and start messaging channels
    if settings.telegram_bot_token:
        tg_adapter = TelegramChannel(
            settings.telegram_bot_token, settings.telegram_webhook_url
        )
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

    if settings.wechat_app_id and settings.wechat_app_secret and settings.wechat_token:
        wechat_adapter = WeChatChannel(
            settings.wechat_app_id,
            settings.wechat_app_secret,
            settings.wechat_token,
            settings.wechat_encoding_aes_key,
        )
        channel_registry.register(wechat_adapter)
        app.include_router(wechat_adapter.router, prefix="/api/channels/wechat")

    # Always register generic webhook for extensibility
    wh_adapter = WebhookChannel()
    channel_registry.register(wh_adapter)
    app.include_router(wh_adapter.router, prefix="/api/channels/webhook")

    await channel_registry.start_all()

    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)
    await start_scheduler()

    from app.core.metrics import arq_queue_depth as _arq_queue_depth

    async def _poll_arq_queue_depth() -> None:
        """Background task: update ARQ queue depth gauge every 30s."""
        from arq import create_pool
        from arq.connections import RedisSettings as _RedisSettings

        pool = await create_pool(_RedisSettings.from_dsn(settings.redis_url))
        try:
            while True:
                try:
                    depth = await pool.zcard("arq:queue")
                    _arq_queue_depth.set(depth)
                except Exception:
                    logger.warning("arq_queue_depth_poll_failed", exc_info=True)
                await asyncio.sleep(30)
        finally:
            await pool.aclose()

    _poller_task = asyncio.create_task(_poll_arq_queue_depth())
    yield
    _poller_task.cancel()
    try:
        await _poller_task
    except asyncio.CancelledError:
        pass
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

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(canvas_router)
app.include_router(chat_router)
app.include_router(chat_files_router)
app.include_router(conversations_router)
app.include_router(folders_router)
app.include_router(notifications_router)
app.include_router(cron_router)
app.include_router(documents_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(memory_router)
app.include_router(search_router)
app.include_router(plugins_router)
app.include_router(personas_router)
app.include_router(public_router)
app.include_router(gateway_router)
app.include_router(tts_router)
app.include_router(voice_router)
app.include_router(usage_router)
app.include_router(webhooks_router)
app.include_router(workflows_router)
app.include_router(keys_router)
app.include_router(organizations_router)
app.include_router(workspaces_router)
app.include_router(invitations_router)
app.include_router(export_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
