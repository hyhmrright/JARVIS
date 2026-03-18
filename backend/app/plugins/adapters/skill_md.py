"""SKILL.md install adapter — downloads and saves .md files."""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 10.0


async def download_skill_md(url: str, dest_path: Path) -> str:
    """Download a .md skill file and write it to dest_path. Returns the content.

    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_FETCH_TIMEOUT
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.text
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")
        logger.info("skill_md_downloaded", url=url, path=str(dest_path))
        return content


def extract_md_title(content: str) -> str | None:
    """Extract the first # heading from Markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None
