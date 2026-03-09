import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.base import GatewayMessage
from app.channels.feishu import FeishuChannel


@pytest.fixture
def feishu_channel():
    return FeishuChannel("app-id", "app-secret")

@pytest.mark.asyncio
async def test_feishu_url_verification(feishu_channel):
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "type": "url_verification",
        "challenge": "test-challenge"
    })

    # Get the endpoint from the router
    handle_webhook = feishu_channel.router.routes[0].endpoint
    response = await handle_webhook(mock_request)

    assert response["challenge"] == "test-challenge"

@pytest.mark.asyncio
async def test_feishu_webhook_message_flow(feishu_channel):
    # Mock tenant token
    feishu_channel._get_tenant_token = AsyncMock(return_value="mock-token")

    # Mock message handler
    handler_called = asyncio.Event()
    async def my_handler(msg: GatewayMessage) -> str:
        assert msg.content == "hello"
        assert msg.sender_id == "user-123"
        handler_called.set()
        return "pong"
    feishu_channel.set_message_handler(my_handler)

    # Mock send_message to avoid real HTTP calls
    feishu_channel.send_message = AsyncMock()

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "hello"}),
                "chat_id": "chat-456",
                "message_id": "msg-789"
            },
            "sender": {"sender_id": {"open_id": "user-123"}}
        }
    })

    handle_webhook = feishu_channel.router.routes[0].endpoint
    await handle_webhook(mock_request)

    # Wait for the async task to trigger handler
    await asyncio.wait_for(handler_called.wait(), timeout=1.0)

    # Check if send_message was called with reply
    feishu_channel.send_message.assert_awaited_once_with(
        "chat-456", "pong", reply_to_id="msg-789"
    )

@pytest.mark.asyncio
async def test_feishu_get_token(feishu_channel):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "tenant_access_token": "new-token",
            "expire": 3600
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        token = await feishu_channel._get_tenant_token()
        assert token == "new-token"
        assert feishu_channel._tenant_token == "new-token"
