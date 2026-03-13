from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.channels.wechat import WeChatChannel

@pytest.fixture
def wechat_channel():
    return WeChatChannel(
        app_id="wx123",
        app_secret="sec123",
        token="token123",
        encoding_aes_key="abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
    )

@pytest.fixture
def client(wechat_channel):
    app = FastAPI()
    app.include_router(wechat_channel.router)
    return TestClient(app)

@pytest.mark.asyncio
async def test_wechat_verify_signature(client):
    # This tests the GET endpoint for verification
    with patch("wechatpy.utils.check_signature") as mock_check:
        mock_check.return_value = None  # means valid
        resp = client.get("/?signature=abc&timestamp=123&nonce=456&echostr=hello")
        assert resp.status_code == 200
        assert resp.text == "hello"

@pytest.mark.asyncio
async def test_wechat_receive_text(client, wechat_channel):
    # Mock message handler
    mock_handler = AsyncMock()
    wechat_channel.set_message_handler(mock_handler)
    
    # Fake XML message
    xml_data = """<xml>
      <ToUserName><![CDATA[gh_123]]></ToUserName>
      <FromUserName><![CDATA[user_456]]></FromUserName>
      <CreateTime>1348831860</CreateTime>
      <MsgType><![CDATA[text]]></MsgType>
      <Content><![CDATA[Hello JARVIS]]></Content>
      <MsgId>1234567890123456</MsgId>
    </xml>"""
    
    with patch("wechatpy.utils.check_signature"):
        resp = client.post("/?signature=abc&timestamp=123&nonce=456", content=xml_data)
        assert resp.status_code == 200
        assert resp.text == "success"
        
        # In a real async loop the task would run. 
        # Here we mock out the actual async queue or rely on sleep.
        import asyncio
        await asyncio.sleep(0.1)
        
        mock_handler.assert_called_once()
        gw_msg = mock_handler.call_args[0][0]
        assert gw_msg.sender_id == "user_456"
        assert gw_msg.channel == "wechat"
        assert gw_msg.content == "Hello JARVIS"

@pytest.mark.asyncio
async def test_wechat_send_message(wechat_channel):
    with patch.object(wechat_channel.client.message, "send_text") as mock_send:
        await wechat_channel.send_message("user_456", "Hello from JARVIS")
        mock_send.assert_called_once_with(user_id="user_456", content="Hello from JARVIS")
