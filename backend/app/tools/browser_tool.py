import base64
import ipaddress
import urllib.parse

import structlog
from langchain_core.tools import tool

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


@tool
async def browser_navigate(url: str, action: str = "extract") -> str:
    """Navigate to a URL and perform the requested action.

    Actions:
    - extract (default): Return page text content.
    - screenshot: Return a confirmation message with page title.

    Args:
        url: The URL to navigate to.
        action: The action to perform (extract or screenshot).
    """
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

    if action not in ("extract", "screenshot"):
        return f"Unknown action: {action}. Supported actions: extract, screenshot."

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            if action == "screenshot":
                title = await page.title()
                await browser.close()
                return f"Page loaded successfully. Title: {title}"

            # action == "extract"
            text = await page.inner_text("body")
            await browser.close()

            if not text.strip():
                return "(empty page)"

            if len(text) > _MAX_TEXT:
                return text[:_MAX_TEXT] + "\n... (truncated)"

            return text

    except ImportError:
        return (
            "playwright not installed. "
            "Run: uv add playwright && playwright install chromium"
        )
    except Exception as e:
        logger.exception("browser_navigate_failed", url=url)
        return f"Browser navigation failed: {e}"


@tool
async def browser_screenshot(url: str) -> str:
    """Take a screenshot of a webpage and return as Base64.

    Use this when you need to see the visual layout of a page.
    """
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot_bytes = await page.screenshot(full_page=True)
            await browser.close()
            base64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"
    except ImportError:
        return (
            "playwright not installed. "
            "Run: uv add playwright && playwright install chromium"
        )
    except Exception as e:
        logger.exception("browser_screenshot_failed", url=url)
        return f"Error taking screenshot of {url}: {e}"


@tool
async def browser_click(url: str, selector: str) -> str:
    """Click an element on a webpage and return the updated text content.

    Use this to interact with buttons, menus, or forms.
    """
    if _is_blocked(url):
        return f"Blocked: URL '{url}' targets a private/internal host."

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.click(selector)
            await page.wait_for_timeout(1000)
            text = await page.inner_text("body")
            await browser.close()
            return f"Clicked {selector}. New content snippet: {text[:5000]}"
    except Exception as e:
        return f"Error clicking {selector}: {e}"
