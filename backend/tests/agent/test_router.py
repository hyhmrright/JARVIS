"""Tests for agent task router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.router import classify_task


@pytest.mark.anyio
async def test_classify_returns_valid_label():
    """classify_task returns one of the five valid labels."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="code"))
        mock_get_llm.return_value = mock_llm

        result = await classify_task(
            "Write a Python script to parse CSV",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "code"


@pytest.mark.anyio
async def test_classify_falls_back_on_unknown_label():
    """Unknown labels from LLM fall back to 'simple'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="gibberish"))
        mock_get_llm.return_value = mock_llm

        result = await classify_task(
            "anything",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "simple"


@pytest.mark.anyio
async def test_classify_falls_back_on_exception():
    """LLM errors fall back to 'simple'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_llm.return_value = mock_llm

        result = await classify_task(
            "anything",
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )
        assert result == "simple"


@pytest.mark.anyio
async def test_classify_truncates_long_messages():
    """Very long messages are truncated before sending to router LLM."""
    captured_messages = []

    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()

        async def capture_invoke(msgs):
            captured_messages.extend(msgs)
            return MagicMock(content="simple")

        mock_llm.ainvoke = capture_invoke
        mock_get_llm.return_value = mock_llm

        long_message = "x" * 10000
        await classify_task(
            long_message,
            provider="deepseek",
            model="deepseek-chat",
            api_key="test",
        )

        # The human message content should be truncated
        human_msg = captured_messages[-1]
        assert len(human_msg.content) <= 2000
