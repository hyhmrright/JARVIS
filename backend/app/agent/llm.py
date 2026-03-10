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


def get_llm(provider: str, model: str, api_key: str, **kwargs: Any) -> BaseChatModel:
    """Create a raw LLM instance for a given provider."""
    # Set reasonable defaults for common params
    if "temperature" not in kwargs:
        kwargs["temperature"] = 0
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
            target_url = kwargs.pop("base_url", settings.ollama_base_url)
            logger.info("creating_ollama_client", model=model, url=target_url)
            return ChatOllama(
                model=model,
                base_url=target_url,
                **kwargs,
            )
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm_with_fallback(
    provider: str, model: str, api_key: str, base_url: str | None = None, **kwargs: Any
) -> BaseChatModel:
    """Get an LLM with automatic failover to predefined backup models."""
    primary_llm = get_llm(provider, model, api_key, base_url=base_url, **kwargs)

    # Define fallback chain based on available settings
    fallbacks: list[BaseChatModel] = []

    # 1. Fallback to OpenAI if not primary
    if provider != "openai" and settings.openai_api_key:
        try:
            fallbacks.append(get_llm("openai", "gpt-4o-mini", settings.openai_api_key))
        except Exception:
            pass

    # 2. Fallback to Anthropic if not primary
    if provider != "anthropic" and settings.anthropic_api_key:
        try:
            fallbacks.append(
                get_llm(
                    "anthropic",
                    "claude-3-haiku-20240307",
                    settings.anthropic_api_key,
                )
            )
        except Exception:
            pass

    if not fallbacks:
        logger.debug("no_fallbacks_available", provider=provider)
        return primary_llm

    logger.info(
        "llm_with_failover_ready", provider=provider, fallback_count=len(fallbacks)
    )
    return primary_llm.with_fallbacks(fallbacks)
