from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models.zhipuai import ChatZhipuAI
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI


def get_llm(provider: str, model: str, api_key: str, **kwargs: Any) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key, **kwargs)  # type: ignore[call-arg]
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key, **kwargs)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key, **kwargs)
        case "zhipuai":
            return ChatZhipuAI(model=model, api_key=api_key, **kwargs)
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm_with_fallback(
    provider: str,
    model: str,
    api_key: str,
    fallback_providers: list[dict] | None = None,
) -> BaseChatModel:
    """Get an LLM instance with automatic failover support (OpenClaw style)."""
    primary_llm = get_llm(provider, model, api_key)

    if not fallback_providers:
        return primary_llm

    fallbacks = []
    for fb in fallback_providers:
        try:
            fb_llm = get_llm(fb["provider"], fb["model"], fb["api_key"])
            fallbacks.append(fb_llm)
        except Exception:
            continue

    if not fallbacks:
        return primary_llm

    return primary_llm.with_fallbacks(fallbacks)
