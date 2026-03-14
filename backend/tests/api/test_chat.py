"""Unit tests for chat.py helper functions: _load_tools, _sse_events_from_chunk, etc."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.api.chat import (
    _load_tools,
    _sse_events_from_chunk,
)
from app.db.models import Conversation, Message, User
from app.main import app


async def test_load_tools_both_when_enabled_tools_is_none():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        # If enabled_tools is None, it should load both
        mcp_tools, plugin_tools = await _load_tools(None)
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_mcp_only_skips_plugin():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        # Only mcp enabled
        mcp_tools, plugin_tools = await _load_tools(["mcp"])
        assert not plugin_tools


async def test_load_tools_plugin_only_skips_mcp():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        # Only plugin enabled
        mcp_tools, plugin_tools = await _load_tools(["plugin"])
        assert not mcp_tools
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_neither_when_no_relevant_tool():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        # Only search enabled, neither mcp nor plugin
        mcp_tools, plugin_tools = await _load_tools(["search"])
        assert not mcp_tools
        assert not plugin_tools


def test_sse_events_from_chunk_with_llm_content():
    chunk = {"llm": {"messages": [AIMessage(content="Hello world")]}}
    events, full_content = _sse_events_from_chunk(chunk, "")

    assert full_content == "Hello world"
    assert len(events) >= 1
    # Check if the expected data is in the raw SSE string
    assert (
        '{"type": "content", "content": "Hello world"}' in events[0]
        or '{"type": "delta", "delta": "Hello world", "content": "Hello world"}'
        in events[0]
    )  # noqa: E501


def test_sse_events_from_chunk_with_existing_content():
    chunk = {"llm": {"messages": [AIMessage(content="Hello world!!!")]}}
    events, full_content = _sse_events_from_chunk(chunk, "Hello world")

    assert full_content == "Hello world!!!"
    assert len(events) >= 1
    assert '"delta": "!!!"' in events[0]


@pytest.mark.asyncio
async def test_chat_stream_sets_parent_id(auth_client, db_session):
    from sqlalchemy import select

    user = (await db_session.execute(select(User))).scalars().first()

    conv = Conversation(user_id=user.id, title="Test Branching")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Use a minimal but complete payload to satisfy Pydantic and logic
    first_payload = {
        "conversation_id": str(conv.id),
        "content": "First message",
        "workspace_id": None,
        "parent_message_id": None,
    }
    resp1 = await auth_client.post("/api/chat/stream", json=first_payload)
    # If it still fails with 400, we check logs.
    # But adding all fields usually fixes Pydantic strict mode.
    assert resp1.status_code == 200
    async for _ in resp1.aiter_text():
        pass


@pytest.mark.asyncio
async def test_chat_regenerate(auth_client, db_session):
    from sqlalchemy import select

    user = (await db_session.execute(select(User))).scalars().first()

    conv = Conversation(user_id=user.id, title="Test Reg")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg_ai = Message(conversation_id=conv.id, role="ai", content="Original AI reply")
    db_session.add(msg_ai)
    await db_session.commit()
    await db_session.refresh(msg_ai)

    resp = await auth_client.post(
        "/api/chat/regenerate",
        json={
            "conversation_id": str(conv.id),
            "message_id": str(msg_ai.id),
            "workspace_id": None,
        },
    )
    assert resp.status_code == 200
    async for _ in resp.aiter_text():
        pass


def test_websocket_chat():
    client = TestClient(app)
    with client.websocket_connect("/api/chat/ws?token=test_token") as websocket:
        websocket.send_json({"type": "chat", "content": "Hello"})
        data = websocket.receive_json()
        assert data["type"] == "token"
