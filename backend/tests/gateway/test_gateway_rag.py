"""Tests for RAG context auto-injection in the gateway router._invoke_agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.gateway.channel_registry import ChannelRegistry
from app.gateway.router import GatewayRouter
from app.gateway.session_manager import SessionManager
from app.rag.retriever import RetrievedChunk


def _make_router() -> GatewayRouter:
    registry = ChannelRegistry()
    adapter = MagicMock()
    adapter.channel_name = "test"
    registry.register(adapter)
    session_mgr = AsyncMock(spec=SessionManager)
    return GatewayRouter(registry, session_mgr)


# Pre-built message list: [system, human]
_PERSONA = SystemMessage(content="You are JARVIS.")
_USER_MSG = HumanMessage(content="Tell me about the architecture")
_BASE_MESSAGES = [_PERSONA, _USER_MSG]


@pytest.mark.asyncio
async def test_invoke_agent_injects_rag_context_when_chunks_found():
    """When retrieve_context returns chunks, a RAG SystemMessage is injected
    between the persona SystemMessage and the first HumanMessage."""
    router = _make_router()

    mock_graph = AsyncMock()
    captured_state: list = []

    async def _capture_invoke(state):  # type: ignore[no-untyped-def]
        captured_state.append(state)
        return {"messages": [AIMessage(content="RAG-enriched reply")]}

    mock_graph.ainvoke.side_effect = _capture_invoke

    fake_chunk = RetrievedChunk(
        document_name="design.pdf",
        content="The design uses a layered architecture.",
        score=0.92,
    )

    with (
        patch("app.gateway.router.resolve_api_key", return_value="fake-openai-key"),
        patch(
            "app.gateway.router.retrieve_context",
            new_callable=AsyncMock,
            return_value=[fake_chunk],
        ),
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        result = await router._invoke_agent(
            provider="openai",
            model_name="gpt-4o-mini",
            api_keys=["fake-key"],
            raw_keys={"openai": "fake-openai-key"},
            enabled_tools=["datetime"],
            user_id="00000000-0000-0000-0000-000000000001",
            lc_messages=list(_BASE_MESSAGES),
            channel="test",
        )

    assert result == "RAG-enriched reply"
    assert len(captured_state) == 1

    messages = captured_state[0].messages
    # First message: persona SystemMessage
    assert isinstance(messages[0], SystemMessage)
    assert "JARVIS" in messages[0].content
    # Second message: injected RAG SystemMessage
    assert isinstance(messages[1], SystemMessage)
    assert "[Knowledge Base Context]" in messages[1].content
    assert "design.pdf" in messages[1].content
    # Third message: original HumanMessage
    assert isinstance(messages[2], HumanMessage)
    assert messages[2].content == "Tell me about the architecture"


@pytest.mark.asyncio
async def test_invoke_agent_skips_rag_when_no_openai_key():
    """When no OpenAI key is available, RAG injection is skipped gracefully."""
    router = _make_router()

    mock_graph = AsyncMock()
    captured_state: list = []

    async def _capture_invoke(state):  # type: ignore[no-untyped-def]
        captured_state.append(state)
        return {"messages": [AIMessage(content="No-RAG reply")]}

    mock_graph.ainvoke.side_effect = _capture_invoke

    with (
        patch(
            "app.gateway.router.resolve_api_key",
            return_value=None,  # No OpenAI key
        ),
        patch(
            "app.gateway.router.retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve,
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        result = await router._invoke_agent(
            provider="deepseek",
            model_name="deepseek-chat",
            api_keys=["deepseek-key"],
            raw_keys={},
            enabled_tools=["datetime"],
            user_id="00000000-0000-0000-0000-000000000002",
            lc_messages=list(_BASE_MESSAGES),
            channel="test",
        )

    assert result == "No-RAG reply"
    # retrieve_context should never have been called
    mock_retrieve.assert_not_called()
    # No RAG SystemMessage injected — persona + human only
    messages = captured_state[0].messages
    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    assert len(system_messages) == 1


@pytest.mark.asyncio
async def test_invoke_agent_skips_rag_when_no_human_message():
    """When lc_messages has no HumanMessage, RAG injection is skipped."""
    router = _make_router()

    mock_graph = AsyncMock()
    captured_state: list = []

    async def _capture_invoke(state):  # type: ignore[no-untyped-def]
        captured_state.append(state)
        return {"messages": [AIMessage(content="System-only reply")]}

    mock_graph.ainvoke.side_effect = _capture_invoke

    with (
        patch("app.gateway.router.resolve_api_key", return_value="fake-openai-key"),
        patch(
            "app.gateway.router.retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve,
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        result = await router._invoke_agent(
            provider="openai",
            model_name="gpt-4o-mini",
            api_keys=["fake-key"],
            raw_keys={"openai": "fake-openai-key"},
            enabled_tools=[],
            user_id="00000000-0000-0000-0000-000000000003",
            lc_messages=[_PERSONA],  # No HumanMessage
            channel="test",
        )

    assert result == "System-only reply"
    mock_retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_agent_continues_on_rag_error():
    """If retrieve_context raises, agent still runs without RAG context."""
    router = _make_router()

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Fallback reply")]
    }

    with (
        patch("app.gateway.router.resolve_api_key", return_value="openai-key"),
        patch(
            "app.gateway.router.retrieve_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Qdrant unavailable"),
        ),
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        result = await router._invoke_agent(
            provider="openai",
            model_name="gpt-4o-mini",
            api_keys=["openai-key"],
            raw_keys={"openai": "openai-key"},
            enabled_tools=[],
            user_id="00000000-0000-0000-0000-000000000004",
            lc_messages=list(_BASE_MESSAGES),
            channel="test",
        )

    assert result == "Fallback reply"
    mock_graph.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_invoke_agent_skips_rag_when_no_chunks_returned():
    """When retrieve_context returns an empty list, no RAG message is added."""
    router = _make_router()

    mock_graph = AsyncMock()
    captured_state: list = []

    async def _capture_invoke(state):  # type: ignore[no-untyped-def]
        captured_state.append(state)
        return {"messages": [AIMessage(content="Empty-rag reply")]}

    mock_graph.ainvoke.side_effect = _capture_invoke

    with (
        patch("app.gateway.router.resolve_api_key", return_value="openai-key"),
        patch(
            "app.gateway.router.retrieve_context",
            new_callable=AsyncMock,
            return_value=[],  # No relevant chunks
        ),
        patch("app.gateway.router.create_graph", return_value=mock_graph),
    ):
        result = await router._invoke_agent(
            provider="openai",
            model_name="gpt-4o-mini",
            api_keys=["openai-key"],
            raw_keys={"openai": "openai-key"},
            enabled_tools=[],
            user_id="00000000-0000-0000-0000-000000000005",
            lc_messages=list(_BASE_MESSAGES),
            channel="test",
        )

    assert result == "Empty-rag reply"
    messages = captured_state[0].messages
    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    assert len(system_messages) == 1  # Only persona, no RAG injection
