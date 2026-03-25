import ipaddress
import urllib.parse

import structlog
from langchain_core.tools import tool

from app.core.config import settings
from app.core.network import _is_private_ip, resolve_and_check_ip
from app.sandbox.manager import SandboxError, SandboxManager

logger = structlog.get_logger(__name__)

_MAX_TEXT = 10000


async def _is_safe_url(url: str) -> bool:
    """Return False if URL resolves to a private/internal IP (SSRF guard)."""
    try:
        hostname = urllib.parse.urlparse(url).hostname
        if not hostname:
            return False
        # Fast path: IP literal
        try:
            ipaddress.ip_address(hostname)
            return not _is_private_ip(hostname)
        except ValueError:
            pass
        # Hostname: resolve and check
        return await resolve_and_check_ip(hostname)
    except Exception:
        return False


async def _run_in_sandbox(script: str) -> str:
    """Execute a Playwright script inside the sandbox."""
    if not settings.sandbox_enabled:
        return (
            "ERROR: Sandbox is disabled. Browser tools require sandboxing for security."
        )

    manager = SandboxManager()
    container_id = None
    try:
        container_id = await manager.create_sandbox(
            user_id="agent", session_id="browser"
        )

        # Escape the script for shell echo
        escaped_script = script.replace("'", "'\\''")
        setup_cmd = f"printf '%s' '{escaped_script}' > /tmp/browser_script.py"
        await manager.exec_in_sandbox(container_id, setup_cmd)

        # Run with playwright
        output = await manager.exec_in_sandbox(
            container_id, "python3 /tmp/browser_script.py", timeout=60
        )
        return output
    except SandboxError as e:
        return f"Sandbox Error: {e}"
    except Exception as e:
        logger.exception("browser_sandbox_failed")
        return f"Browser execution failed: {e}"
    finally:
        if container_id:
            await manager.destroy_sandbox(container_id)


@tool
async def browser_navigate(url: str) -> str:
    """Navigate to a URL and extract the page text content.

    Use this to read the content of a website.
    """
    if not await _is_safe_url(url):
        return "Error: URL is not allowed (private/internal address)"

    script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.goto('{url}', wait_until='networkidle', timeout=30000)
            text = await page.inner_text('body')
            print(text[:{_MAX_TEXT}])
            await browser.close()
        except Exception as e:
            print(f'Error: {{e}}')

if __name__ == '__main__':
    asyncio.run(main())
"""
    return await _run_in_sandbox(script)


@tool
async def browser_screenshot(url: str) -> str:
    """Take a screenshot of a webpage and return as Base64 data URL.

    Use this when you need to see the visual layout of a page.
    """
    if not await _is_safe_url(url):
        return "Error: URL is not allowed (private/internal address)"

    script = f"""
import asyncio
import base64
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.set_viewport_size({{'width': 1280, 'height': 800}})
            await page.goto('{url}', wait_until='networkidle', timeout=30000)
            screenshot_bytes = await page.screenshot(full_page=False)
            base64_str = base64.b64encode(screenshot_bytes).decode('utf-8')
            print(f'data:image/png;base64,{{base64_str}}')
            await browser.close()
        except Exception as e:
            print(f'Error: {{e}}')

if __name__ == '__main__':
    asyncio.run(main())
"""
    return await _run_in_sandbox(script)


@tool
async def browser_click(url: str, selector: str) -> str:
    """Click an element on a webpage and return the updated text content.

    Use this to interact with buttons, menus, or forms.
    """
    if not await _is_safe_url(url):
        return "Error: URL is not allowed (private/internal address)"

    script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            await page.goto('{url}', wait_until='networkidle', timeout=30000)
            await page.click('{selector}')
            await asyncio.sleep(2) # Wait for animation/load
            text = await page.inner_text('body')
            print(text[:{_MAX_TEXT}])
            await browser.close()
        except Exception as e:
            print(f'Error: {{e}}')

if __name__ == '__main__':
    asyncio.run(main())
"""
    return await _run_in_sandbox(script)
