from unittest.mock import patch

import pytest

from app.agent.llm import get_llm


def test_get_llm_deepseek_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatDeepSeek") as mock:
        get_llm("deepseek", "deepseek-chat", "key")
        mock.assert_called_once_with(
            model="deepseek-chat", api_key="key", temperature=0, max_retries=2
        )


def test_get_llm_openai_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatOpenAI") as mock:
        get_llm("openai", "gpt-4o-mini", "key")
        mock.assert_called_once_with(
            model="gpt-4o-mini", api_key="key", temperature=0, max_retries=2
        )


def test_get_llm_anthropic_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatAnthropic") as mock:
        get_llm("anthropic", "claude-3-5-haiku-20241022", "key")
        mock.assert_called_once_with(
            model="claude-3-5-haiku-20241022", api_key="key", temperature=0, max_retries=2
        )


def test_get_llm_zhipuai_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatZhipuAI") as mock:
        get_llm("zhipuai", "glm-4-flash", "test-key")
        mock.assert_called_once_with(
            model="glm-4-flash", api_key="test-key", temperature=0, max_retries=2
        )


def test_get_llm_zhipuai_model_variants() -> None:
    """Verify different GLM model strings are passed through unchanged."""
    for model in ("glm-4", "glm-4.7", "glm-4.7-FlashX", "glm-5", "glm-z1-flash"):
        with patch("app.agent.llm.ChatZhipuAI") as mock:
            get_llm("zhipuai", model, "key")
            mock.assert_called_once_with(
                model=model, api_key="key", temperature=0, max_retries=2
            )


def test_get_llm_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown provider: fakeai"):
        get_llm("fakeai", "model", "key")
