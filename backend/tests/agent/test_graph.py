from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import create_graph


async def test_graph_returns_ai_message():
    mock_response = AIMessage(content="Hello!")
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("app.agent.graph.get_llm", return_value=mock_llm):
        graph = create_graph(provider="deepseek", model="deepseek-chat", api_key="test")
        result = await graph.ainvoke({"messages": [HumanMessage(content="Hi")]})
    assert result["messages"][-1].content == "Hello!"
