import base64
import ipaddress
import urllib.parse

import structlog
from langchain_core.tools import tool

from app.core.config import settings
from app.sandbox.manager import SandboxError, SandboxManager

logger = structlog.get_logger(__name__)

_MAX_TEXT = 10000
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_blocked(url: str) -> bool:
    """Return True if the URL targets a private/internal host (SSRF protection)."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if host in _BLOCKED_HOSTS:
            return True
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return False


async def _run_in_sandbox(script: str) -> str:
    """Execute a Playwright script inside the sandbox."""
    if not settings.sandbox_enabled:
        return (
            "ERROR: Sandbox is disabled. "
            "Browser tools require sandboxing for security."
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
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

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
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

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
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

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
