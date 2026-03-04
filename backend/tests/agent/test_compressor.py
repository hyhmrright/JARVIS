from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.compressor import compact_messages


@pytest.fixture()
def mock_llm():
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="Summary of old messages")
    return llm


@pytest.mark.asyncio
async def test_below_threshold_returns_unchanged(mock_llm):
    msgs = [
        SystemMessage(content="sys"),
        HumanMessage(content="hi"),
        AIMessage(content="hello"),
    ]
    with patch("app.agent.compressor.get_llm", return_value=mock_llm):
        result = await compact_messages(
            msgs, provider="test", model="m", api_key="k", threshold=50_000
        )
    assert result is msgs
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_above_threshold_compresses(mock_llm):
    sys_msg = SystemMessage(content="system prompt")
    old_msgs = [HumanMessage(content="x" * 10_000) for _ in range(8)]
    recent = [HumanMessage(content="recent"), AIMessage(content="reply")]
    all_msgs = [sys_msg, *old_msgs, *recent]

    with patch("app.agent.compressor.get_llm", return_value=mock_llm):
        result = await compact_messages(
            all_msgs,
            provider="test",
            model="m",
            api_key="k",
            threshold=1_000,
            keep_recent=2,
        )

    # system + summary + 2 recent
    assert len(result) == 4
    assert isinstance(result[0], SystemMessage)
    assert "[Conversation summary]" in result[1].content
    assert result[2].content == "recent"
    assert result[3].content == "reply"
    mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_system_message_preserved(mock_llm):
    sys_msg = SystemMessage(content="important system prompt")
    msgs = [sys_msg] + [HumanMessage(content="x" * 5_000) for _ in range(20)]

    with patch("app.agent.compressor.get_llm", return_value=mock_llm):
        result = await compact_messages(
            msgs,
            provider="test",
            model="m",
            api_key="k",
            threshold=100,
            keep_recent=3,
        )

    assert isinstance(result[0], SystemMessage)
    assert result[0].content == "important system prompt"


@pytest.mark.asyncio
async def test_keep_recent_not_compressed(mock_llm):
    sys_msg = SystemMessage(content="sys")
    msgs = [sys_msg] + [HumanMessage(content="x" * 5_000) for _ in range(4)]

    with patch("app.agent.compressor.get_llm", return_value=mock_llm):
        result = await compact_messages(
            msgs,
            provider="test",
            model="m",
            api_key="k",
            threshold=100,
            keep_recent=6,
        )

    # Only 4 non-system messages, keep_recent=6 so nothing to compress
    assert result is msgs
    mock_llm.ainvoke.assert_not_called()
