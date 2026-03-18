"""SKILL.md install adapter — downloads and saves .md files."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 10.0
_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _validate_url(url: str) -> None:
    """Raise ValueError if the URL scheme is not http or https."""
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"Only http/https URLs are allowed, got: {url!r}")


async def download_skill_md(url: str, dest_path: Path) -> str:
    """Download a .md skill file and write it to dest_path. Returns the content.

    Raises ValueError for non-http URLs.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    _validate_url(url)
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_FETCH_TIMEOUT
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > _MAX_SIZE:
            raise ValueError(f"Response too large ({len(response.content)} bytes)")
        content = response.text
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(dest_path.write_text, content, "utf-8")
        logger.info("skill_md_downloaded", url=url, path=str(dest_path))
        return content


def extract_md_title(content: str) -> str | None:
    """Extract the first # heading from Markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None
