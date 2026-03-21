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
async def test_chat_regenerate_updates_agent_session_status(auth_client, db_session):
    """AgentSession status must be updated to 'completed' after regenerate stream."""
    from app.core.security import decode_access_token

    token = auth_client.headers.get("Authorization").split(" ")[1]
    user_id = uuid.UUID(decode_access_token(token))

    conv = Conversation(user_id=user_id, title="Test AgentSession Lifecycle")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg_ai = Message(conversation_id=conv.id, role="ai", content="Original")
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
        yield {"llm": {"messages": [AIMessage(content="Regenerated")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    execute_calls: list = []
    added_objects: list = []
    tracking_session = MagicMock()
    tracking_session.__aenter__ = AsyncMock(return_value=tracking_session)
    tracking_session.__aexit__ = AsyncMock(return_value=None)
    tracking_session.begin = MagicMock(return_value=tracking_session)
    tracking_session.scalar = AsyncMock(return_value=None)

    def _track_add(obj: object) -> None:
        added_objects.append(obj)

    tracking_session.add = MagicMock(side_effect=_track_add)

    async def _mock_flush() -> None:
        # Simulate SQLAlchemy applying column defaults on flush
        for obj in added_objects:
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()

    tracking_session.flush = AsyncMock(side_effect=_mock_flush)

    async def _track_execute(stmt, *args, **kwargs):
        execute_calls.append(stmt)

    tracking_session.execute = AsyncMock(side_effect=_track_execute)

    with (
        patch("app.api.chat.get_llm_config", new_callable=AsyncMock) as mock_get_llm,
        patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify,
        patch("app.api.chat._build_expert_graph") as mock_build_graph,
        patch("app.api.chat.compact_messages", new_callable=AsyncMock) as mock_compact,
        patch("app.api.chat.build_rag_context", new_callable=AsyncMock) as mock_rag,
        patch("app.api.chat.AsyncSessionLocal", return_value=tracking_session),
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

    # execute() must have been called with an UPDATE targeting AgentSession
    from sqlalchemy.sql.dml import Update

    assert any(isinstance(s, Update) for s in execute_calls)


@pytest.mark.asyncio
async def test_model_override_replaces_model_name(auth_client, db_session):
    """model_override in the request body should shadow the user's settings model."""
    from app.core.security import decode_access_token

    token = auth_client.headers.get("Authorization").split(" ")[1]
    user_id = uuid.UUID(decode_access_token(token))
    conv = Conversation(user_id=user_id, title="Override Test")
    db_session.add(conv)
    await db_session.commit()

    captured_model: list[str] = []

    base_llm = ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=None,
        persona_override=None,
        raw_keys={},
        base_url=None,
    )

    async def mock_astream(*args, **kwargs):
        yield {"llm": {"messages": [AIMessage(content="overridden")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    def capture_build_graph(route, *args, **kwargs):
        assert route == "main"
        captured_model.append(kwargs["model"])
        return mock_graph

    with (
        patch("app.api.chat.get_llm_config", new_callable=AsyncMock) as mock_get_llm,
        patch("app.api.chat.classify_task", new_callable=AsyncMock) as mock_classify,
        patch("app.api.chat._build_expert_graph", side_effect=capture_build_graph),
        patch("app.api.chat.compact_messages", new_callable=AsyncMock) as mock_compact,
        patch("app.api.chat.build_rag_context", new_callable=AsyncMock) as mock_rag,
    ):
        mock_get_llm.return_value = base_llm
        mock_classify.return_value = "main"
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        resp = await auth_client.post(
            "/api/chat/stream",
            json={
                "conversation_id": str(conv.id),
                "content": "hello",
                "model_override": "deepseek-reasoner",
            },
        )
        assert resp.status_code == 200
        async for _ in resp.aiter_text():
            pass

    assert captured_model and captured_model[0] == "deepseek-reasoner"


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
