from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.search_tool import create_web_search_tool


@pytest.fixture()
def search_tool():
    return create_web_search_tool(api_key="tvly-test-key")


def _mock_tavily_response() -> dict:
    """Return a realistic Tavily search response."""
    return {
        "results": [
            {
                "title": "Python (programming language)",
                "url": "https://en.wikipedia.org/wiki/Python",
                "content": "Python is a high-level programming language.",
                "score": 0.95,
            },
            {
                "title": "Python Tutorial",
                "url": "https://docs.python.org/3/tutorial/",
                "content": "The Python tutorial introduces basic concepts.",
                "score": 0.88,
            },
        ],
    }


async def test_web_search_returns_formatted_results(search_tool):
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_mock_tavily_response())
    with patch("app.tools.search_tool.AsyncTavilyClient", return_value=mock_client):
        result = await search_tool.ainvoke({"query": "Python programming"})
    assert "Python is a high-level" in result
    assert "Python Tutorial" in result
    mock_client.search.assert_awaited_once()


async def test_web_search_no_results(search_tool):
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value={"results": []})
    with patch("app.tools.search_tool.AsyncTavilyClient", return_value=mock_client):
        result = await search_tool.ainvoke({"query": "xyznonexistent"})
    assert "no results" in result.lower()


async def test_web_search_handles_error(search_tool):
    mock_client = MagicMock()
    mock_client.search = AsyncMock(side_effect=Exception("API error"))
    with patch("app.tools.search_tool.AsyncTavilyClient", return_value=mock_client):
        result = await search_tool.ainvoke({"query": "test"})
    assert "error" in result.lower()


async def test_web_search_tool_has_correct_name(search_tool):
    assert search_tool.name == "web_search"


async def test_web_search_closes_over_api_key():
    """Different API keys produce independent tool instances."""
    tool_a = create_web_search_tool(api_key="key-a")
    tool_b = create_web_search_tool(api_key="key-b")

    mock_client_a = MagicMock()
    mock_client_a.search = AsyncMock(return_value=_mock_tavily_response())
    mock_client_b = MagicMock()
    mock_client_b.search = AsyncMock(return_value=_mock_tavily_response())

    with patch(
        "app.tools.search_tool.AsyncTavilyClient",
        side_effect=[mock_client_a, mock_client_b],
    ) as mock_cls:
        await tool_a.ainvoke({"query": "q"})
        await tool_b.ainvoke({"query": "q"})
        # Verify each tool was created with its own key
        assert mock_cls.call_count == 2
        mock_cls.assert_any_call(api_key="key-a")
        mock_cls.assert_any_call(api_key="key-b")


async def test_web_search_max_results_default(search_tool):
    """Default max_results should be 5."""
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=_mock_tavily_response())
    with patch("app.tools.search_tool.AsyncTavilyClient", return_value=mock_client):
        await search_tool.ainvoke({"query": "test"})
    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["max_results"] == 5
