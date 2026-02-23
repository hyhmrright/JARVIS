from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI


def get_llm(provider: str, model: str, api_key: str) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown provider: {provider}")
