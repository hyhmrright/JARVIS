"""Agent context management service.

Consolidates RAG context building, message formatting, and
conversation history compression previously inside AgentEngine.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from sqlalchemy import select

from app.agent.compressor import compact_messages
from app.agent.persona import build_system_prompt
from app.core.security import resolve_api_key
from app.db.models import Message
from app.rag.context import build_rag_context

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.llm_config import ResolvedLLMConfig
    from app.db.models import Conversation

logger = structlog.get_logger(__name__)


class ContextService:
    """Orchestrates agent context: history, RAG, and compression."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build_messages(
        self,
        user_id: uuid.UUID,
        conv: Conversation,
        llm: ResolvedLLMConfig,
        content: str,
        *,
        compress: bool = True,
    ) -> list[BaseMessage]:
        """Construct the complete message history for the LLM.

        Includes: System prompt, RAG context, and historical messages.
        Optionally compresses history using LLM-based summarization.
        """
        rows = await self._db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )

        role_map = {"human": HumanMessage, "ai": AIMessage}
        msgs: list[BaseMessage] = [
            SystemMessage(content=build_system_prompt(llm.persona_override))
        ]

        # Load history
        for r in rows.all():
            cls = role_map.get(r.role)
            if cls:
                msgs.append(cls(content=r.content))

        # Build RAG
        openai_key = resolve_api_key("openai", llm.raw_keys)
        rag = await build_rag_context(str(user_id), content, openai_key)
        if rag:
            msgs.insert(1, SystemMessage(content=rag))

        if compress:
            return await compact_messages(
                msgs,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
            )
        return msgs
