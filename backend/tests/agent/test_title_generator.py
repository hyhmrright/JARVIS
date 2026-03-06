"""Tests for conversation title generator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.title_generator import generate_title

_CALL_KWARGS = {
    "user_message": "帮我写一个 Python function 解析 CSV",
    "ai_reply": "好的，这里是代码示例...",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "test",
}


@pytest.mark.asyncio
async def test_generate_title_returns_short_string():
    """generate_title returns a non-empty string within expected length."""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="Python CSV 解析器")
        )
        mock_get_llm.return_value = mock_llm

        result = await generate_title(**_CALL_KWARGS)

    assert isinstance(result, str)
    assert len(result) <= 50


@pytest.mark.asyncio
async def test_generate_title_strips_whitespace():
    """Leading/trailing whitespace is stripped from the generated title."""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="  CSV Parser  "))
        mock_get_llm.return_value = mock_llm

        result = await generate_title(**_CALL_KWARGS)

    assert result == "CSV Parser"


@pytest.mark.asyncio
async def test_generate_title_returns_none_on_empty_response():
    """Empty LLM response returns None instead of an empty string."""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="   "))
        mock_get_llm.return_value = mock_llm

        result = await generate_title(**_CALL_KWARGS)

    assert result is None


@pytest.mark.asyncio
async def test_generate_title_falls_back_on_error():
    """LLM error returns None and does not propagate the exception."""
    with patch("app.agent.title_generator.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_llm.return_value = mock_llm

        result = await generate_title(**_CALL_KWARGS)

    assert result is None
