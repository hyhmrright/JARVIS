"""Browser automation tool using Playwright for JavaScript-heavy pages."""

import structlog
from langchain_core.tools import tool

from app.tools.web_fetch_tool import is_safe_url

logger = structlog.get_logger(__name__)

_MAX_TEXT = 8000


@tool
async def browser_navigate(url: str, action: str = "extract") -> str:
    """Navigate to a URL using a headless browser and extract content.

    Use this for JavaScript-heavy pages that web_fetch cannot handle.
    The page is fully rendered before extraction.

    Args:
        url: The URL to navigate to.
        action: "extract" to get page text, "screenshot" to confirm it loaded.
    """
    if not is_safe_url(url):
        return f"Blocked: URL '{url}' targets a private or internal address."

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "Browser tool unavailable: playwright not installed."

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=15000)

            if not is_safe_url(page.url):
                return f"Blocked: redirected to private address '{page.url}'."

            if action == "extract":
                text = await page.inner_text("body")
                if len(text) > _MAX_TEXT:
                    text = text[:_MAX_TEXT] + "\n... (truncated)"
                return text or "(empty page)"
            if action == "screenshot":
                title = await page.title()
                return f"Page loaded successfully. Title: {title}"
            return f"Unknown action: {action}. Use 'extract' or 'screenshot'."
        except Exception as exc:
            logger.warning("browser_navigate_error", url=url, error=str(exc)[:200])
            return f"Browser navigation failed: {exc}"
        finally:
            await browser.close()
