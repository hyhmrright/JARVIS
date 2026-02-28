"""Tests for browser_navigate tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.browser_tool import _MAX_TEXT, browser_navigate


def _make_mocks(
    *, inner_text: str = "Hello World", title: str = "Test Page"
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build mock page, browser, and playwright context manager."""
    page = AsyncMock()
    page.inner_text.return_value = inner_text
    page.title.return_value = title
    page.url = "https://example.com"

    browser = AsyncMock()
    browser.new_page.return_value = page

    pw_instance = AsyncMock()
    pw_instance.chromium.launch.return_value = browser

    pw_cm = AsyncMock()
    pw_cm.__aenter__.return_value = pw_instance
    pw_cm.__aexit__.return_value = None

    return page, browser, pw_cm


@pytest.mark.asyncio
async def test_extract_returns_page_text() -> None:
    page, _browser, pw_cm = _make_mocks(inner_text="Some content")

    with patch("playwright.async_api.async_playwright", return_value=pw_cm):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "extract"}
        )

    assert result == "Some content"
    page.inner_text.assert_awaited_once_with("body")


@pytest.mark.asyncio
async def test_extract_truncates_long_text() -> None:
    long_text = "x" * (_MAX_TEXT + 500)
    _page, _browser, pw_cm = _make_mocks(inner_text=long_text)

    with patch("playwright.async_api.async_playwright", return_value=pw_cm):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "extract"}
        )

    assert result.endswith("\n... (truncated)")
    assert len(result) == _MAX_TEXT + len("\n... (truncated)")


@pytest.mark.asyncio
async def test_extract_empty_page() -> None:
    _page, _browser, pw_cm = _make_mocks(inner_text="")

    with patch("playwright.async_api.async_playwright", return_value=pw_cm):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "extract"}
        )

    assert result == "(empty page)"


@pytest.mark.asyncio
async def test_screenshot_returns_title() -> None:
    _page, _browser, pw_cm = _make_mocks(title="My Page")

    with patch("playwright.async_api.async_playwright", return_value=pw_cm):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "screenshot"}
        )

    assert result == "Page loaded successfully. Title: My Page"


@pytest.mark.asyncio
async def test_unknown_action_returns_error() -> None:
    _page, _browser, pw_cm = _make_mocks()

    with patch("playwright.async_api.async_playwright", return_value=pw_cm):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "bad_action"}
        )

    assert "Unknown action: bad_action" in result


@pytest.mark.asyncio
async def test_navigation_error_returns_message() -> None:
    page_mock = AsyncMock()
    page_mock.goto.side_effect = TimeoutError("Navigation timed out")

    browser_mock = AsyncMock()
    browser_mock.new_page.return_value = page_mock

    pw_instance = AsyncMock()
    pw_instance.chromium.launch.return_value = browser_mock

    pw_cm2 = AsyncMock()
    pw_cm2.__aenter__.return_value = pw_instance
    pw_cm2.__aexit__.return_value = None

    with patch("playwright.async_api.async_playwright", return_value=pw_cm2):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "extract"}
        )

    assert "Browser navigation failed" in result
    assert "Navigation timed out" in result


@pytest.mark.asyncio
async def test_blocks_private_urls() -> None:
    """Internal/private URLs should be blocked (SSRF protection)."""
    result = await browser_navigate.ainvoke(
        {"url": "http://169.254.169.254/metadata", "action": "extract"}
    )
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_blocks_localhost_urls() -> None:
    """Localhost URLs should be blocked (SSRF protection)."""
    result = await browser_navigate.ainvoke(
        {"url": "http://localhost:8000/api/settings", "action": "extract"}
    )
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_import_error_returns_graceful_message() -> None:
    real_import = __import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "playwright.async_api":
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = await browser_navigate.ainvoke(
            {"url": "https://example.com", "action": "extract"}
        )

    assert "playwright not installed" in result
