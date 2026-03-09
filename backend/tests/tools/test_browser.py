from unittest.mock import AsyncMock, patch

import pytest

from app.tools.browser_tool import (
    browser_click,
    browser_navigate,
    browser_screenshot,
)


@pytest.mark.asyncio
async def test_browser_navigate_sandbox_flow():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(
            side_effect=["OK", "Mock Page Content"]
        )
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_navigate.ainvoke("https://example.com")

        assert "Mock Page Content" in result
        assert mock_manager.create_sandbox.called
        # Check if setup_cmd was called (the printf one)
        setup_call = mock_manager.exec_in_sandbox.call_args_list[0]
        assert "printf" in setup_call.args[1]
        assert "playwright" in setup_call.args[1]

        # Check if execution was called
        exec_call = mock_manager.exec_in_sandbox.call_args_list[1]
        assert "python3 /tmp/browser_script.py" in exec_call.args[1]


@pytest.mark.asyncio
async def test_browser_blocked_host():
    result = await browser_navigate.ainvoke("http://localhost:8000")
    assert "Blocked" in result


@pytest.mark.asyncio
async def test_browser_screenshot_sandbox_flow():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(
            side_effect=["OK", "data:image/png;base64,mockdata"]
        )
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_screenshot.ainvoke("https://example.com")

        assert "data:image/png;base64" in result


@pytest.mark.asyncio
async def test_browser_click_sandbox_flow():
    with (
        patch("app.tools.browser_tool.settings") as mock_settings,
        patch("app.tools.browser_tool.SandboxManager") as mock_manager_cls,
    ):
        mock_settings.sandbox_enabled = True
        mock_manager = mock_manager_cls.return_value
        mock_manager.create_sandbox = AsyncMock(return_value="cnt-123")
        mock_manager.exec_in_sandbox = AsyncMock(side_effect=["OK", "Updated Content"])
        mock_manager.destroy_sandbox = AsyncMock()

        result = await browser_click.ainvoke(
            {"url": "https://example.com", "selector": "button#login"}
        )

        assert "Updated Content" in result
        setup_call = mock_manager.exec_in_sandbox.call_args_list[0]
        assert "page.click" in setup_call.args[1]
        assert "button#login" in setup_call.args[1]
