from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.rag.retriever import RetrievedChunk, maybe_inject_rag_context


@pytest.mark.anyio
async def test_ollama_rag_injection_and_invocation():
    """验证 RAG 上下文注入后，Ollama 模型能接收到这些消息。"""

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is in the document?"),
    ]

    # 模拟检索到的块
    mock_chunks = [
        RetrievedChunk(
            document_name="test.txt", content="The secret code is 1234.", score=0.95
        )
    ]

    with patch(
        "app.rag.retriever.retrieve_context", AsyncMock(return_value=mock_chunks)
    ):
        # 注入上下文
        enriched_messages = await maybe_inject_rag_context(
            messages, "What is in the document?", "user123", "openai_key"
        )

        assert len(enriched_messages) == 3
        assert isinstance(enriched_messages[1], SystemMessage)
        assert "The secret code is 1234." in enriched_messages[1].content

        # 模拟 ChatOllama 调用
        mock_llm = MagicMock(spec=ChatOllama)
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content="The document says the secret code is 1234.")
        )

        # 调用模型
        response = await mock_llm.ainvoke(enriched_messages)

        assert "1234" in response.content
        # 验证模型接收到了所有 3 条消息
        mock_llm.ainvoke.assert_called_with(enriched_messages)


@pytest.mark.anyio
async def test_maybe_inject_rag_context_no_key():
    """验证没有 OpenAI 密钥时（用于嵌入），不注入上下文。"""
    messages = [HumanMessage(content="Hi")]

    result = await maybe_inject_rag_context(messages, "Hi", "user123", None)

    assert result == messages
