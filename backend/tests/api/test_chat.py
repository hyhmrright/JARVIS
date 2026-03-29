"""Unit tests for chat.py helper functions: _load_tools, _sse_events_from_chunk, etc."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select

from app.api.chat import chat_regenerate, chat_stream
from app.api.chat.graph_builder import load_tools as _load_tools
from app.api.chat.message_builder import (
    build_langchain_messages as _build_langchain_messages,
)
from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import sse_events_from_chunk as _sse_events_from_chunk
from app.api.deps import ResolvedLLMConfig
from app.db.models import AgentSession, Conversation, Message

_RAW_CHAT_STREAM = getattr(chat_stream, "__wrapped__", chat_stream)
_RAW_CHAT_REGENERATE = getattr(chat_regenerate, "__wrapped__", chat_regenerate)


def _user_id_from_auth_client(auth_client) -> uuid.UUID:
    from app.core.security import decode_access_token

    token = auth_client.headers.get("Authorization").split(" ")[1]
    return uuid.UUID(decode_access_token(token))


def _user_stub(user_id: uuid.UUID):
    return type("UserStub", (), {"id": user_id})()


async def test_load_tools_both_when_enabled_tools_is_none():
    with patch("app.api.chat.graph_builder.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(None)
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_mcp_only_skips_plugin():
    with patch("app.api.chat.graph_builder.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(["mcp"])
        assert not plugin_tools


async def test_load_tools_plugin_only_skips_mcp():
    with patch("app.api.chat.graph_builder.plugin_registry") as mock_plugin_reg:
        mock_plugin_reg.get_all_tools.return_value = ["plugin_tool"]
        mcp_tools, plugin_tools = await _load_tools(["plugin"])
        assert not mcp_tools
        assert plugin_tools == ["plugin_tool"]


async def test_load_tools_neither_when_no_relevant_tool():
    with patch("app.api.chat.graph_builder.plugin_registry") as mock_plugin_reg:
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


def test_build_langchain_messages_parses_serialized_tool_message():
    tool_msg = Message(
        conversation_id=uuid.uuid4(),
        role="tool",
        content='{"tool_call_id":"call_1","name":"web_search","content":"done"}',
    )

    lc_messages = _build_langchain_messages([tool_msg])

    assert len(lc_messages) == 1
    parsed = lc_messages[0]
    assert isinstance(parsed, ToolMessage)
    assert parsed.tool_call_id == "call_1"
    assert parsed.name == "web_search"
    assert parsed.content == "done"


class _StreamRequest:
    async def is_disconnected(self) -> bool:
        return False


class _PatchedChatSession:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def begin(self):
        return self

    def add(self, instance):
        self._session.add(instance)

    async def flush(self):
        await self._session.flush()

    async def scalar(self, *args, **kwargs):
        return await self._session.scalar(*args, **kwargs)

    async def execute(self, *args, **kwargs):
        return await self._session.execute(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        return await self._session.scalars(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self._session.get(*args, **kwargs)

    async def commit(self):
        await self._session.commit()


async def _drain_streaming_response(response) -> str:
    chunks: list[str] = []
    for _ in range(16):
        try:
            chunk = await asyncio.wait_for(anext(response.body_iterator), timeout=0.5)
        except StopAsyncIteration:
            break
        except TimeoutError:
            break
        chunks.append(chunk)
        if '"type": "done"' in chunk or '"type":"done"' in chunk:
            break
    return "".join(chunks)


@pytest.mark.asyncio
async def test_chat_stream_sets_parent_id(auth_client, db_session):
    user_id = _user_id_from_auth_client(auth_client)

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
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch("app.api.chat.routes.build_expert_graph") as mock_build_graph,
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
        patch(
            "app.api.chat.routes.AsyncSessionLocal",
            return_value=_PatchedChatSession(db_session),
        ),
        patch(
            "app.agent.title_generator.generate_title",
            new=AsyncMock(return_value="Test Branching"),
        ),
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_STREAM(
            _StreamRequest(),
            ChatRequest(**payload),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)


@pytest.mark.asyncio
async def test_chat_stream_uses_active_leaf_when_parent_missing(
    auth_client, db_session
):
    user_id = _user_id_from_auth_client(auth_client)

    conv = Conversation(user_id=user_id, title="Active Leaf Fallback")
    db_session.add(conv)
    await db_session.flush()

    first_human = Message(
        conversation_id=conv.id,
        role="human",
        content="My name is Alice.",
    )
    db_session.add(first_human)
    await db_session.flush()

    first_ai = Message(
        conversation_id=conv.id,
        role="ai",
        content="Your name is Alice.",
        parent_id=first_human.id,
    )
    db_session.add(first_ai)
    await db_session.flush()

    conv.active_leaf_id = first_ai.id
    await db_session.commit()

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
        yield {"llm": {"messages": [AIMessage(content="You are Alice.")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    with (
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch("app.api.chat.routes.build_expert_graph") as mock_build_graph,
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
        patch(
            "app.api.chat.routes.AsyncSessionLocal",
            return_value=_PatchedChatSession(db_session),
        ),
        patch(
            "app.agent.title_generator.generate_title",
            new=AsyncMock(return_value="Active Leaf Fallback"),
        ),
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_STREAM(
            _StreamRequest(),
            ChatRequest(conversation_id=conv.id, content="What is my name?"),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)

    rows = await db_session.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = rows.all()
    assert messages[-2].role == "human"
    assert messages[-2].parent_id == first_ai.id


@pytest.mark.asyncio
async def test_chat_stream_persists_tool_transcript(auth_client, db_session):
    user_id = _user_id_from_auth_client(auth_client)

    conv = Conversation(user_id=user_id, title="Tool Transcript")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

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
        ai_tool = AIMessage(content="")
        ai_tool.tool_calls = [
            {"name": "web_search", "args": {"query": "alice"}, "id": "call_1"}
        ]
        yield {"llm": {"messages": [ai_tool]}}
        yield {
            "tools": {
                "messages": [
                    ToolMessage(
                        content="Alice result",
                        name="web_search",
                        tool_call_id="call_1",
                    )
                ]
            }
        }
        yield {"llm": {"messages": [AIMessage(content="Alice is your name.")]}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream

    with (
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch("app.api.chat.routes.build_expert_graph") as mock_build_graph,
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
        patch(
            "app.api.chat.routes.AsyncSessionLocal",
            return_value=_PatchedChatSession(db_session),
        ),
        patch(
            "app.agent.title_generator.generate_title",
            new=AsyncMock(return_value="Tool Transcript"),
        ),
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_STREAM(
            _StreamRequest(),
            ChatRequest(conversation_id=conv.id, content="Search for Alice"),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)

    rows = await db_session.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = rows.all()
    assert [msg.role for msg in messages] == ["human", "ai", "tool", "ai"]
    assert messages[1].tool_calls is not None
    assert messages[1].tool_calls[0]["name"] == "web_search"
    assert '"tool_call_id": "call_1"' in messages[2].content
    assert messages[3].parent_id == messages[2].id


@pytest.mark.asyncio
async def test_chat_regenerate_updates_agent_session_status(auth_client, db_session):
    """AgentSession status must be updated to 'completed' after regenerate stream."""
    user_id = _user_id_from_auth_client(auth_client)

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

    tracking_session = _PatchedChatSession(db_session)

    with (
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch("app.api.chat.routes.build_expert_graph") as mock_build_graph,
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
        patch("app.api.chat.routes.AsyncSessionLocal", return_value=tracking_session),
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_REGENERATE(
            _StreamRequest(),
            RegenerateRequest(conversation_id=conv.id, message_id=msg_ai.id),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)

    agent_sessions = (
        await db_session.scalars(
            select(AgentSession)
            .where(AgentSession.conversation_id == conv.id)
            .order_by(AgentSession.created_at)
        )
    ).all()
    assert agent_sessions
    assert agent_sessions[-1].status == "completed"


@pytest.mark.asyncio
async def test_model_override_replaces_model_name(auth_client, db_session):
    """model_override in the request body should shadow the user's settings model."""
    user_id = _user_id_from_auth_client(auth_client)
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

    def capture_build_graph(route, config, *args, **kwargs):
        assert route == "main"
        captured_model.append(config.llm.model_name)
        return mock_graph

    with (
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch(
            "app.api.chat.routes.build_expert_graph", side_effect=capture_build_graph
        ),
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
    ):
        mock_get_llm.return_value = base_llm
        mock_classify.return_value = "main"
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_STREAM(
            _StreamRequest(),
            ChatRequest(
                conversation_id=conv.id,
                content="hello",
                model_override="deepseek-reasoner",
            ),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)

    assert captured_model and captured_model[0] == "deepseek-reasoner"


@pytest.mark.asyncio
async def test_chat_regenerate(auth_client, db_session):
    user_id = _user_id_from_auth_client(auth_client)

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
        patch(
            "app.api.chat.routes.get_llm_config", new_callable=AsyncMock
        ) as mock_get_llm,
        patch(
            "app.api.chat.routes.classify_task", new_callable=AsyncMock
        ) as mock_classify,
        patch("app.api.chat.routes.build_expert_graph") as mock_build_graph,
        patch(
            "app.api.chat.routes.compact_messages", new_callable=AsyncMock
        ) as mock_compact,
        patch(
            "app.api.chat.context.build_rag_context", new_callable=AsyncMock
        ) as mock_rag,
    ):
        mock_get_llm.return_value = mock_llm
        mock_classify.return_value = "main"
        mock_build_graph.return_value = mock_graph
        mock_compact.side_effect = lambda msgs, **kwargs: msgs
        mock_rag.return_value = ""

        response = await _RAW_CHAT_REGENERATE(
            _StreamRequest(),
            RegenerateRequest(conversation_id=conv.id, message_id=msg_ai.id),
            _user_stub(user_id),
            db_session,
        )
        await _drain_streaming_response(response)
