"""Tests for agent task router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.router import classify_task

_CALL_KWARGS = {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "test",
}


@pytest.mark.anyio
async def test_classify_returns_valid_label():
    """classify_task returns one of the five valid labels from LLM."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="code"))
        mock_get_llm.return_value = mock_llm

        # Message has action word "帮" → falls through rule layer to LLM
        result = await classify_task("请帮我协调这个数据处理工作流", **_CALL_KWARGS)
        assert result == "code"
        mock_get_llm.assert_called_once()


@pytest.mark.anyio
async def test_classify_falls_back_on_unknown_label():
    """Unknown labels from LLM fall back to 'simple'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="gibberish"))
        mock_get_llm.return_value = mock_llm

        # Message has action word "帮" → falls through rule layer to LLM
        result = await classify_task("请帮我评估一下这个方案的可行性", **_CALL_KWARGS)
        assert result == "simple"
        mock_get_llm.assert_called_once()


@pytest.mark.anyio
async def test_classify_falls_back_on_exception():
    """LLM errors fall back to 'simple'."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_llm.return_value = mock_llm

        # Message has action word "帮" → falls through rule layer to LLM
        result = await classify_task("请帮我评估一下这个方案的可行性", **_CALL_KWARGS)
        assert result == "simple"
        mock_get_llm.assert_called_once()


@pytest.mark.anyio
async def test_classify_truncates_long_messages():
    """Very long messages are truncated before sending to router LLM."""
    captured_messages: list = []

    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()

        async def capture_invoke(msgs):
            captured_messages.extend(msgs)
            return MagicMock(content="simple")

        mock_llm.ainvoke = capture_invoke
        mock_get_llm.return_value = mock_llm

        long_message = "x" * 10000
        await classify_task(long_message, **_CALL_KWARGS)

        human_msg = captured_messages[-1]
        assert len(human_msg.content) <= 2000


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("帮我写一个 Python function 解析 CSV", "code"),
        ("帮我搜索一下最新的 AI 论文", "research"),
        ("帮我写一篇关于量子计算的文章", "writing"),
        ("你好", "simple"),
    ],
    ids=["code_keywords", "research_keywords", "writing_keywords", "short_simple"],
)
async def test_rule_based_classify_skips_llm(message: str, expected: str):
    """Rule layer classifies directly without calling the LLM."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        result = await classify_task(message, **_CALL_KWARGS)
        assert result == expected
        mock_get_llm.assert_not_called()


@pytest.mark.anyio
async def test_rule_based_classify_falls_through_to_llm():
    """When no rule matches, the LLM is called for classification."""
    with patch("app.agent.router.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="complex"))
        mock_get_llm.return_value = mock_llm

        result = await classify_task(
            "请帮我协调团队的多个跨部门项目，并生成汇报材料", **_CALL_KWARGS
        )
        assert result == "complex"
        mock_get_llm.assert_called_once()
