"""Web page content extraction tool."""

import asyncio
import ipaddress
from urllib.parse import urlparse

import httpx
import trafilatura
from langchain_core.tools import tool

from app.core.network import _is_private_ip, resolve_and_check_ip

_MAX_CONTENT_LENGTH = 8000  # chars, ~2000 tokens


async def is_safe_url(url: str) -> bool:
    """Reject URLs targeting internal/private networks (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
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


@tool
async def web_fetch(url: str) -> str:
    """Fetch a web page and extract its readable text content.

    Use this to read articles, documentation, or any web page.
    """
    if not await is_safe_url(url):
        return "Blocked: cannot fetch internal or private network URLs."

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "JARVIS/1.0"})
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return f"Failed to fetch URL: {exc}"

    extracted = await asyncio.to_thread(
        trafilatura.extract, resp.text, include_links=True, include_tables=True
    )
    if not extracted:
        return "Could not extract readable content from the page."

    if len(extracted) > _MAX_CONTENT_LENGTH:
        extracted = extracted[:_MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
    return extracted
