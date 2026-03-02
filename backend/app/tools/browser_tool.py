import base64

import structlog
from langchain_core.tools import tool
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)


@tool
async def browser_navigate(url: str) -> str:
    """Navigate to a URL and return the text content.

    Use this for information retrieval from the web.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            text = await page.inner_text("body")
            await browser.close()
            return text[:10000]  # Limit response size
    except Exception as e:
        logger.exception("browser_navigate_failed", url=url)
        return f"Error navigating to {url}: {str(e)}"


@tool
async def browser_screenshot(url: str) -> str:
    """Take a screenshot of a webpage and return as Base64.

    Use this when you need to see the visual layout of a page (e.g. for CSS debugging
    or capturing charts).
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Full page screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            await browser.close()

            base64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"
    except Exception as e:
        logger.exception("browser_screenshot_failed", url=url)
        return f"Error taking screenshot of {url}: {str(e)}"


@tool
async def browser_click(url: str, selector: str) -> str:
    """Click an element on a webpage and return the updated text content.

    Use this to interact with buttons, menus, or forms.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.click(selector)
            await page.wait_for_timeout(1000)  # Wait for potential transition
            text = await page.inner_text("body")
            await browser.close()
            return f"Clicked {selector}. New content snippet: {text[:5000]}"
    except Exception as e:
        return f"Error clicking {selector}: {str(e)}"
