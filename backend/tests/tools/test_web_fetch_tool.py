from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.tools.web_fetch_tool import _MAX_CONTENT_LENGTH, _is_safe_url, web_fetch


@pytest.fixture()
def _mock_httpx_success():
    """Patch httpx.AsyncClient to return a successful HTML response."""
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.text = "<html><body><p>Hello world article.</p></body></html>"
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.tools.web_fetch_tool.httpx.AsyncClient", return_value=mock_client):
        yield mock_client


async def test_web_fetch_returns_extracted_content(_mock_httpx_success):
    with patch(
        "app.tools.web_fetch_tool.trafilatura.extract",
        return_value="Extracted article text",
    ):
        result = await web_fetch.ainvoke({"url": "https://example.com"})
    assert result == "Extracted article text"


async def test_web_fetch_truncates_long_content(_mock_httpx_success):
    long_text = "x" * (_MAX_CONTENT_LENGTH + 500)
    with patch(
        "app.tools.web_fetch_tool.trafilatura.extract",
        return_value=long_text,
    ):
        result = await web_fetch.ainvoke({"url": "https://example.com"})
    assert len(result) < len(long_text)
    assert result.endswith("[Content truncated]")


async def test_web_fetch_extraction_fails(_mock_httpx_success):
    with patch(
        "app.tools.web_fetch_tool.trafilatura.extract",
        return_value=None,
    ):
        result = await web_fetch.ainvoke({"url": "https://example.com"})
    assert "could not extract" in result.lower()


async def test_web_fetch_http_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "404",
            request=httpx.Request("GET", "https://x.com"),
            response=httpx.Response(404),
        )
    )
    with patch("app.tools.web_fetch_tool.httpx.AsyncClient", return_value=mock_client):
        result = await web_fetch.ainvoke({"url": "https://x.com/missing"})
    assert "failed to fetch" in result.lower()


async def test_web_fetch_connection_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    with patch("app.tools.web_fetch_tool.httpx.AsyncClient", return_value=mock_client):
        result = await web_fetch.ainvoke({"url": "https://unreachable.test"})
    assert "failed to fetch" in result.lower()


async def test_web_fetch_blocks_private_urls():
    result = await web_fetch.ainvoke({"url": "http://127.0.0.1:8080/admin"})
    assert "blocked" in result.lower()


async def test_web_fetch_blocks_internal_urls():
    result = await web_fetch.ainvoke({"url": "http://192.168.1.1/secret"})
    assert "blocked" in result.lower()


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com", True),
        ("http://127.0.0.1", False),
        ("http://localhost:8080", False),
        ("http://10.0.0.1/admin", False),
        ("http://192.168.1.1", False),
        ("ftp://example.com", False),
        ("http://[::1]/admin", False),
    ],
)
def test_is_safe_url(url: str, expected: bool):
    assert _is_safe_url(url) == expected


async def test_web_fetch_tool_name():
    assert web_fetch.name == "web_fetch"
