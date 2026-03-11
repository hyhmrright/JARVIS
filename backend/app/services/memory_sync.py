import asyncio
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Conversation, Message
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


def _yaml_quote(value: str) -> str:
    """Return a single-quoted YAML string, escaping single quotes within."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


async def sync_conversation_to_markdown(conversation_id: uuid.UUID) -> None:
    """Export a conversation to a local Markdown file (Obsidian compatible)."""
    try:
        async with AsyncSessionLocal() as db:
            conv = await db.get(Conversation, conversation_id)
            if not conv:
                return

            # Fetch all messages for this conversation
            result = await db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            messages = result.all()

            # Ensure directory exists
            sync_dir = Path(settings.memory_sync_dir)
            sync_dir.mkdir(parents=True, exist_ok=True)

            # File naming: date-id.md (safe for all filesystems)
            date_str = conv.created_at.strftime("%Y-%m-%d")
            file_path = sync_dir / f"{date_str}-{conversation_id}.md"

            lines = []
            # YAML Frontmatter
            lines.append("---")
            lines.append(f"title: {_yaml_quote(conv.title)}")
            lines.append(f"id: {conversation_id}")
            lines.append(f"date: {conv.created_at.isoformat()!r}")
            lines.append(f"updated: {conv.updated_at.isoformat()!r}")
            lines.append("tags: [jarvis, memory]")
            lines.append("---\n")

            for msg in messages:
                role = "USER" if msg.role == "human" else "JARVIS"
                lines.append(f"### {role} ({msg.created_at.strftime('%H:%M:%S')})")
                lines.append(f"{msg.content}\n")

            content = "\n".join(lines)
            # Async write
            await asyncio.to_thread(file_path.write_text, content)
            logger.info("memory_sync_completed", path=str(file_path))

    except Exception:
        logger.exception("memory_sync_failed", conversation_id=str(conversation_id))
