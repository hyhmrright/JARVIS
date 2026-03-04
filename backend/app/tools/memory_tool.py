from pathlib import Path

import structlog
from langchain_core.tools import tool

from app.core.config import settings

logger = structlog.get_logger(__name__)


@tool
def search_local_memory(query: str) -> str:
    """Search through the local JARVIS conversation memory (Markdown files).

    Use this to find details from past conversations that might not be in the
    current conversation history or vector store.
    """
    memory_dir = Path(settings.memory_sync_dir)
    if not memory_dir.exists():
        return "No local memory found."

    results = []
    try:
        # Simple search across all .md files in the memory dir
        for md_file in memory_dir.glob("*.md"):
            content = md_file.read_text()
            if query.lower() in content.lower():
                idx = content.lower().find(query.lower())
                start = max(0, idx - 200)
                end = min(len(content), idx + 500)
                snippet = content[start:end]
                results.append(f"--- From {md_file.name} ---\n...{snippet}...")

            if len(results) >= 5:  # Limit results
                break

        if not results:
            return f"No matches found for '{query}' in local memory."

        return "\n\n".join(results)
    except Exception as e:
        logger.exception("local_memory_search_failed")
        return f"Error searching memory: {str(e)}"


@tool
def read_memory_file(filename: str) -> str:
    """Read the full content of a specific memory file by name."""
    memory_dir = Path(settings.memory_sync_dir)
    file_path = memory_dir / filename

    # Basic security check to prevent path traversal
    if not file_path.exists() or not str(file_path.resolve()).startswith(
        str(memory_dir.resolve())
    ):
        return "File not found or access denied."

    try:
        return file_path.read_text()
    except Exception as e:
        return f"Error reading file: {str(e)}"
