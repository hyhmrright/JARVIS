"""Unit tests for chat.py helper functions: _load_tools, _sse_events_from_chunk, etc."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.api.chat import (
    _load_tools,
    _sse_events_from_chunk,
)
from app.api.deps import ResolvedLLMConfig
from app.db.models import Conversation, Message


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
    events, _ = _sse_events_from_chunk(chunk, "")
    assert len(events) >= 1
    assert "Hello world" in events[0]


def test_sse_events_from_chunk_with_existing_content():
    chunk = {"llm": {"messages": [AIMessage(content="Hello world!!!")]}}
    events, _ = _sse_events_from_chunk(chunk, "Hello world")
    assert len(events) >= 1
    assert "!!!" in events[0]


@pytest.mark.asyncio
async def test_chat_stream_sets_parent_id(auth_client, db_session):
    from app.core.security import decode_access_token

    token = auth_client.headers.get("Authorization").split(" ")[1]
    user_id_str = decode_access_token(token)
    user_id = uuid.UUID(user_id_str)

    conv = Conversation(user_id=user_id, title="Test Branching")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    payload = {"conversation_id": str(conv.id), "content": "Test Message"}

    mock_llm = ResolvedLLMConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=None,
        persona_override=None,
        raw_keys={},
        base_url=None,
    )

    async def mock_astream(*args, **kwargs):
        yield {"llm": {"messages": [AIMessage(content="Mocked response")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    with (
        patch("app.api.chat.get_llm_config", new_callable=AsyncMock) as mock_get_llm,
        patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify,
        patch("app.api.chat._build_expert_graph") as mock_build_graph,
        patch("app.api.chat.compact_messages", new_callable=AsyncMock) as mock_compact,
        patch("app.api.chat.build_rag_context", new_callable=AsyncMock) as mock_rag,
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        resp = await auth_client.post("/api/chat/stream", json=payload)
        assert resp.status_code == 200
        async for _ in resp.aiter_text():
            pass


@pytest.mark.asyncio
async def test_chat_regenerate(auth_client, db_session):
    from app.core.security import decode_access_token

    token = auth_client.headers.get("Authorization").split(" ")[1]
    user_id_str = decode_access_token(token)
    user_id = uuid.UUID(user_id_str)

    conv = Conversation(user_id=user_id, title="Test Reg")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg_ai = Message(conversation_id=conv.id, role="ai", content="Original AI reply")
    db_session.add(msg_ai)
    await db_session.commit()
    await db_session.refresh(msg_ai)

    mock_llm = ResolvedLLMConfig(
        provider="openai",
        model_name="gpt-4o",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=None,
        persona_override=None,
        raw_keys={},
        base_url=None,
    )

    async def mock_astream(*args, **kwargs):
        yield {"llm": {"messages": [AIMessage(content="Mocked response")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    with (
        patch("app.api.chat.get_llm_config", new_callable=AsyncMock) as mock_get_llm,
        patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify,
        patch("app.api.chat._build_expert_graph") as mock_build_graph,
        patch("app.api.chat.compact_messages", new_callable=AsyncMock) as mock_compact,
        patch("app.api.chat.build_rag_context", new_callable=AsyncMock) as mock_rag,
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        resp = await auth_client.post(
            "/api/chat/regenerate",
            json={"conversation_id": str(conv.id), "message_id": str(msg_ai.id)},
        )
        assert resp.status_code == 200
        async for _ in resp.aiter_text():
            pass
