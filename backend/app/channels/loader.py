from fastapi import FastAPI

from app.channels.discord import DiscordChannel
from app.channels.feishu import FeishuChannel
from app.channels.slack import SlackChannel
from app.channels.telegram import TelegramChannel
from app.channels.webhook import WebhookChannel
from app.channels.wechat import WeChatChannel
from app.channels.whatsapp import WhatsAppChannel
from app.core.config import settings
from app.gateway.channel_registry import ChannelRegistry


async def load_and_register_channels(app: FastAPI, registry: ChannelRegistry) -> None:
    """从配置初始化并注册所有的消息渠道。"""
    if settings.telegram_bot_token:
        tg_adapter = TelegramChannel(
            settings.telegram_bot_token, settings.telegram_webhook_url
        )
        registry.register(tg_adapter)
        app.include_router(tg_adapter.router, prefix="/api/channels/telegram")

    if settings.feishu_app_id and settings.feishu_app_secret:
        fs_adapter = FeishuChannel(settings.feishu_app_id, settings.feishu_app_secret)
        registry.register(fs_adapter)
        app.include_router(fs_adapter.router, prefix="/api/channels/feishu")

    if settings.discord_bot_token:
        registry.register(DiscordChannel(settings.discord_bot_token))

    if settings.slack_bot_token and settings.slack_app_token:
        registry.register(
            SlackChannel(settings.slack_bot_token, settings.slack_app_token)
        )

    if settings.whatsapp_account_sid and settings.whatsapp_auth_token:
        ws_adapter = WhatsAppChannel(
            settings.whatsapp_account_sid,
            settings.whatsapp_auth_token,
            settings.whatsapp_from_number,
        )
        registry.register(ws_adapter)
        app.include_router(ws_adapter.router, prefix="/api/channels/whatsapp")

    if settings.wechat_app_id and settings.wechat_app_secret and settings.wechat_token:
        wechat_adapter = WeChatChannel(
            settings.wechat_app_id,
            settings.wechat_app_secret,
            settings.wechat_token,
            settings.wechat_encoding_aes_key,
        )
        registry.register(wechat_adapter)
        app.include_router(wechat_adapter.router, prefix="/api/channels/wechat")

    wh_adapter = WebhookChannel()
    registry.register(wh_adapter)
    app.include_router(wh_adapter.router, prefix="/api/channels/webhook")
