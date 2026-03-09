from unittest.mock import AsyncMock, patch

import pytest

from app.tools.browser_tool import browser_navigate, browser_screenshot


@pytest.mark.asyncio
async def test_extract_returns_page_text():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        # setup_cmd success, then output
        mock_manager.exec_in_sandbox = AsyncMock(side_effect=["OK", "Some content"])
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_navigate.ainvoke("https://example.com")
        assert result == "Some content"


@pytest.mark.asyncio
async def test_extract_empty_page():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(side_effect=["OK", ""])
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_navigate.ainvoke("https://example.com")
        assert result == ""


@pytest.mark.asyncio
async def test_screenshot_returns_data_url():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(
            side_effect=["OK", "data:image/png;base64,abc"]
        )
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_screenshot.ainvoke("https://example.com")
        assert "data:image/png;base64" in result


@pytest.mark.asyncio
async def test_navigation_error_returns_message():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(
            side_effect=["OK", "Error: failed to navigate"]
        )
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_navigate.ainvoke("https://example.com")
        assert "Error: failed to navigate" in result
