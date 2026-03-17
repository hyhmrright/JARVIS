# backend/tests/agent/test_llm_fallback.py
"""Tests for LLM fallback chain error reporting."""

from unittest.mock import MagicMock, patch

import pytest


def test_fallback_init_failure_logs_provider_name() -> None:
    """When a fallback provider fails to init, the WARNING log must include
    the provider name and error details as structured fields.

    Uses patch on the structlog logger directly (caplog does not capture
    structlog output unless the stdlib bridge is explicitly configured).
    """
    from app.agent.llm import get_llm_with_fallback

    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.deepseek_api_key = None
        mock_settings.ollama_base_url = None

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            primary = MagicMock()
            primary.with_fallbacks = MagicMock(return_value=primary)

            def side_effect(provider: str, *args: object, **kwargs: object) -> MagicMock:
                if provider == "openai":
                    raise ValueError("Connection refused to OpenAI")
                return primary

            mock_get_llm.side_effect = side_effect

            with patch("app.agent.llm.logger") as mock_logger:
                get_llm_with_fallback("deepseek", "deepseek-chat", "key")

        # The warning must be called with fallback_provider="openai"
        warning_calls = mock_logger.warning.call_args_list
        assert any(
            call.kwargs.get("fallback_provider") == "openai" for call in warning_calls
        ), f"Expected warning with fallback_provider='openai', got: {warning_calls}"


def test_all_providers_fail_raises_llm_init_error() -> None:
    """When ALL providers (primary + all fallbacks) fail to init,
    get_llm_with_fallback must raise LLMInitError with the failure chain.
    """
    from app.agent.llm import LLMInitError, get_llm_with_fallback

    with patch("app.agent.llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.deepseek_api_key = "ds-key"
        mock_settings.ollama_base_url = None

        with patch("app.agent.llm.get_llm") as mock_get_llm:
            # All providers fail
            mock_get_llm.side_effect = ValueError("provider unreachable")

            with pytest.raises(LLMInitError) as exc_info:
                get_llm_with_fallback("deepseek", "deepseek-chat", "key")

            err = exc_info.value
            assert hasattr(err, "failures"), (
                "LLMInitError must have a 'failures' attribute"
            )
            assert len(err.failures) > 0, "failures list must not be empty"
            provider_names = [name for name, _ in err.failures]
            assert any(name in provider_names for name in ["deepseek", "openai"])
