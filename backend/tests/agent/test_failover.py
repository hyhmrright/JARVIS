import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.llm import get_llm_with_fallback


@pytest.mark.asyncio
async def test_llm_failover_logic():
    """验证当主模型失败时，是否能切换到备用模型。"""

    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-backup"
        mock_settings.anthropic_api_key = ""

        # Actually LangChain's with_fallbacks handles the retry logic.
        # We want to test if get_llm_with_fallback returns a model with fallbacks.

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            mock_primary = MagicMock()
            mock_primary.with_fallbacks = MagicMock(return_value="fallback_wrapper")

            mock_backup = MagicMock()

            mock_get_llm.side_effect = [mock_primary, mock_backup]

            llm = get_llm_with_fallback("deepseek", "deepseek-chat", "sk-123")

            assert llm == "fallback_wrapper"
            mock_primary.with_fallbacks.assert_called_once()
            # The backup should be OpenAI based on settings
            backup_call = mock_get_llm.call_args_list[1]
            assert backup_call.args[0] == "openai"


@pytest.mark.asyncio
async def test_llm_no_fallback_if_no_keys():
    """验证当没有备用 Key 时，不创建 fallback 链。"""
    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        mock_settings.anthropic_api_key = ""

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            mock_primary = MagicMock()
            mock_get_llm.return_value = mock_primary

            llm = get_llm_with_fallback("deepseek", "deepseek-chat", "sk-123")

            assert llm == mock_primary
            assert (
                not hasattr(llm, "with_fallbacks") or not llm.with_fallbacks.called
            )
