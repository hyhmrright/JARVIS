from unittest.mock import MagicMock, patch

from langchain_ollama import ChatOllama

from app.agent.llm import get_llm


def test_get_llm_ollama():
    provider = "ollama"
    model = "llama3"
    api_key = ""  # Ollama doesn't need an API key

    with patch("app.core.llm_factory.ChatOllama") as mock_chat_ollama:
        mock_instance = MagicMock(spec=ChatOllama)
        mock_chat_ollama.return_value = mock_instance

        llm = get_llm(provider, model, api_key, temperature=0.7)

        # Verify ChatOllama was called with correct parameters
        mock_chat_ollama.assert_called_once()
        args, kwargs = mock_chat_ollama.call_args
        assert kwargs["model"] == model
        assert kwargs["temperature"] == 0.7
        assert llm == mock_instance


def test_get_llm_ollama_default_params():
    provider = "ollama"
    model = "mistral"
    api_key = ""

    with patch("app.core.llm_factory.ChatOllama") as mock_chat_ollama:
        get_llm(provider, model, api_key)

        # Verify default temperature=0.7 and max_retries=2
        _, kwargs = mock_chat_ollama.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_retries"] == 2
