"""Unit tests for chat.py helper functions: _load_tools, _sse_events_from_chunk, etc."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from app.api.chat import (
    _format_sse,
    _load_tools,
    _sse_events_from_chunk,
)
from app.db.models import Conversation, Message, User, UserRole  # noqa: F401
from app.main import app


async def test_load_tools_both_when_enabled_tools_is_none():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(None)
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_mcp_only_skips_plugin():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(["mcp"])
        assert not plugin_tools


async def test_load_tools_plugin_only_skips_mcp():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(["plugin"])
        assert not mcp_tools
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_neither_when_no_relevant_tool():
    with patch("app.api.chat.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(["search"])
        assert not mcp_tools
        assert not plugin_tools


def test_sse_events_from_chunk_with_llm_content():
    chunk = {"llm": {"messages": [AIMessage(content="Hello world")]}}
    events, full_content = _sse_events_from_chunk(chunk, "")

    assert full_content == "Hello world"
    assert len(events) >= 1
    # Check for content regardless of delta/content type
    assert "Hello world" in events[0]


def test_sse_events_from_chunk_with_existing_content():
    chunk = {"llm": {"messages": [AIMessage(content="Hello world!!!")]}}
    events, full_content = _sse_events_from_chunk(chunk, "Hello world")

    assert full_content == "Hello world!!!"
    assert len(events) >= 1
    assert "!!!" in events[0]


@pytest.mark.asyncio
async def test_chat_stream_sets_parent_id(auth_client, db_session):
    from sqlalchemy import select
    user = (await db_session.execute(select(User))).scalars().first()
    
    conv = Conversation(user_id=user.id, title="Test Branching")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    first_payload = {
        "conversation_id": str(conv.id),
        "content": "First message",
        "workspace_id": None,
        "parent_message_id": None
    }
    
    # Global patch to avoid any LLM logic during integration test
    with patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify:
        mock_classify.return_value = "main"
        resp1 = await auth_client.post("/api/chat/stream", json=first_payload)
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

    with patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify:
        mock_classify.return_value = "main"
        resp = await auth_client.post(
            "/api/chat/regenerate",
            json={
                "conversation_id": str(conv.id), 
                "message_id": str(msg_ai.id),
                "workspace_id": None
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
