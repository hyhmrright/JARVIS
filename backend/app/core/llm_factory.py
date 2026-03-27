"""LLM factory functions shared across agent and scheduler layers.

Placed in ``app.core`` so modules below the agent layer (e.g. the scheduler)
can construct LLM clients without creating an upward dependency on
``app.agent``.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMInitError(Exception):
    """Raised when all LLM providers (primary + fallbacks) fail to initialize.

    Attributes:
        failures: List of (provider_name, exception) for each failed provider.
    """

    def __init__(self, failures: list[tuple[str, Exception]]) -> None:
        self.failures = failures
        summary = "; ".join(f"{p}: {e}" for p, e in failures)
        super().__init__(f"All LLM providers failed to initialize: {summary}")


def get_llm(
    provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
) -> BaseChatModel:
    """Factory function to return a LangChain ChatModel instance."""
    kwargs.setdefault("temperature", 0.7)
    if "max_retries" not in kwargs:
        kwargs["max_retries"] = 2

    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key, **kwargs)
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key, **kwargs)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key, **kwargs)
        case "zhipuai":
            return ChatZhipuAI(model=model, api_key=api_key, **kwargs)
        case "ollama":
            # ChatOllama does not accept max_retries — strip it before passing kwargs.
            kwargs.pop("max_retries", None)
            target_url = base_url or settings.ollama_base_url
            logger.info("creating_ollama_client", model=model, url=target_url)
            return ChatOllama(model=model, base_url=target_url, **kwargs)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm_with_fallback(
    provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
) -> BaseChatModel:
    """Get an LLM with automatic failover to predefined backup models.

    Raises:
        LLMInitError: if the primary provider AND all fallbacks fail to init.
    """
    failures: list[tuple[str, Exception]] = []

    try:
        primary_llm = get_llm(provider, model, api_key, base_url=base_url, **kwargs)
    except Exception as exc:
        logger.warning(
            "primary_provider_init_failed",
            primary_provider=provider,
            error=str(exc),
        )
        failures.append((provider, exc))
        primary_llm = None

    fallbacks: list[BaseChatModel] = []

    _fallback_candidates: list[tuple[str, str, str | None]] = [
        ("openai", "gpt-4o-mini", settings.openai_api_key),
        ("deepseek", "deepseek-chat", settings.deepseek_api_key),
    ]
    for fb_provider, fb_model, fb_key in _fallback_candidates:
        if fb_provider == provider or not fb_key:
            continue
        try:
            fallbacks.append(get_llm(fb_provider, fb_model, fb_key, **kwargs))
        except Exception as exc:
            logger.warning(
                "fallback_provider_init_failed",
                fallback_provider=fb_provider,
                error=str(exc),
            )
            failures.append((fb_provider, exc))

    if primary_llm is None and not fallbacks:
        last_exc = failures[-1][1] if failures else None
        raise LLMInitError(failures) from last_exc

    if primary_llm is None:
        primary_llm = fallbacks.pop(0)

    if not fallbacks:
        logger.debug("no_fallbacks_available", provider=provider)
        return primary_llm

    logger.info(
        "llm_with_failover_ready", provider=provider, fallback_count=len(fallbacks)
    )
    return primary_llm.with_fallbacks(fallbacks)
