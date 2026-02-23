from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import create_graph


async def test_graph_returns_ai_message():
    mock_response = AIMessage(content="Hello!")
    mock_instance = AsyncMock()
    mock_instance.ainvoke.return_value = mock_response
    with patch("app.agent.graph.get_llm", return_value=mock_instance):
        graph = create_graph(provider="deepseek", model="deepseek-chat", api_key="test")
        result = await graph.ainvoke({"messages": [HumanMessage(content="Hi")]})
    assert result["messages"][-1].content == "Hello!"
