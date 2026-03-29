"""Chat context builder — extracts setup logic from chat_stream().

``build_chat_context()`` performs all the stateful setup that happens before
the SSE streaming generator starts: input sanitization, conversation lookup,
persona/workflow resolution, human-message persistence, message-history
walking, system prompt construction, memory injection, and RAG injection.

Keeping this in a separate module makes the logic unit-testable without
spinning up the full SSE pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from dataclasses import replace as dc_replace

import structlog
from fastapi import HTTPException
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.persona import build_system_prompt
from app.api.chat.message_builder import (
    build_langchain_messages,
    build_memory_message,
    walk_message_chain,
)
from app.api.chat.schemas import ChatRequest
from app.api.settings import PROVIDER_MODELS
from app.core.llm_config import ResolvedLLMConfig
from app.core.sanitizer import sanitize_user_input
from app.core.security import resolve_api_key
from app.db.models import Conversation, Message, User
from app.rag.context import build_rag_context

logger = structlog.get_logger(__name__)


@dataclass
class ChatContext:
    """All inputs the SSE generator needs after setup is complete."""

    lc_messages: list[BaseMessage]
    conv_id: uuid.UUID
    human_msg_id: uuid.UUID | None
    user_content: str
    is_consent: bool
    approved: bool | None
    is_first_exchange: bool
    parent_message_id: uuid.UUID | None
    workflow_dsl: dict | None = None
    openai_key: str | None = None
    # carry the (possibly mutated) llm config so routes.py can use it
    llm: ResolvedLLMConfig | None = None
    # allow routes.py to read conv.active_leaf_id after the function returns
    extra: dict = field(default_factory=dict)


async def build_chat_context(  # noqa: C901
    body: ChatRequest,
    user: User,
    db: AsyncSession,
    llm: ResolvedLLMConfig,
) -> ChatContext:
    """Resolve conversation state and return a ready-to-stream ChatContext."""
    # ── model override ────────────────────────────────────────────────────────
    if body.model_override:
        allowed = PROVIDER_MODELS.get(llm.provider, [])
        if allowed and body.model_override not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"model '{body.model_override}' not valid for '{llm.provider}'",
            )
        llm = dc_replace(llm, model_name=body.model_override)

    # ── input sanitization ────────────────────────────────────────────────────
    user_content = sanitize_user_input(body.content)
    is_consent = user_content.startswith("[CONSENT:")
    approved: bool | None = None
    if is_consent:
        approved = "ALLOW" in user_content

    # ── conversation lookup ───────────────────────────────────────────────────
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    # ── persona / workflow resolution ─────────────────────────────────────────
    if not is_consent:
        from app.db.models import Persona

        if conv.persona_id:
            _persona = await db.scalar(
                select(Persona).where(Persona.id == conv.persona_id)
            )
            if _persona:
                if not conv.persona_override:
                    conv.persona_override = _persona.system_prompt
                    await db.commit()
                if _persona.model_name:
                    llm = dc_replace(llm, model_name=_persona.model_name)
                if _persona.temperature is not None:
                    llm = dc_replace(llm, temperature=_persona.temperature)
                if _persona.enabled_tools is not None:
                    llm = dc_replace(llm, enabled_tools=_persona.enabled_tools)
        elif body.persona_id or body.workflow_dsl:
            _msg_count = await db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conv.id)
            )
            if (_msg_count or 0) == 0:
                if body.persona_id:
                    _persona = await db.scalar(
                        select(Persona).where(
                            Persona.id == body.persona_id,
                            Persona.user_id == user.id,
                        )
                    )
                    if _persona:
                        conv.persona_override = _persona.system_prompt
                        await db.commit()
                if body.workflow_dsl:
                    conv.workflow_dsl = body.workflow_dsl
                    await db.commit()
    elif body.workflow_dsl and not is_consent:
        # Store workflow DSL for a new conversation when the consent branch
        # was not taken.  (Mirrors the original elif in routes.py.)
        _msg_count = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        if (_msg_count or 0) == 0:
            conv.workflow_dsl = body.workflow_dsl
            await db.commit()

    parent_message_id = body.parent_message_id or conv.active_leaf_id

    # ── human message persistence ─────────────────────────────────────────────
    human_msg_id: uuid.UUID | None = None
    if not is_consent:
        final_content = user_content
        if body.file_context:
            final_content = (
                f"[Attached file: {body.file_context.filename}]\n"
                f"{body.file_context.extracted_text}\n\n----- \n{user_content}"
            )
        human_msg = Message(
            conversation_id=conv.id,
            role="human",
            content=final_content,
            image_urls=body.image_urls,
            parent_id=parent_message_id,
        )
        db.add(human_msg)
        await db.commit()
        await db.refresh(human_msg)
        human_msg_id = human_msg.id

    # ── message history ───────────────────────────────────────────────────────
    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    all_conv_messages = history_rows.all()

    msg_dict = {msg.id: msg for msg in all_conv_messages}

    start_id = human_msg_id if not is_consent else parent_message_id
    if not start_id and all_conv_messages:
        start_id = all_conv_messages[-1].id

    all_history = walk_message_chain(msg_dict, start_id)
    lc_messages: list[BaseMessage] = build_langchain_messages(all_history)

    # ── system prompt ─────────────────────────────────────────────────────────
    if llm.system_prompt:
        system_msg = SystemMessage(content=llm.system_prompt)
    else:
        system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    # ── memory injection ──────────────────────────────────────────────────────
    _mem_msg = await build_memory_message(db, user.id)
    if _mem_msg:
        lc_messages = [lc_messages[0], _mem_msg, *lc_messages[1:]]

    # ── first-exchange detection ──────────────────────────────────────────────
    is_first_exchange = sum(1 for m in lc_messages if isinstance(m, AIMessage)) == 0

    # ── RAG injection ─────────────────────────────────────────────────────────
    openai_key = resolve_api_key("openai", llm.raw_keys)
    last_ai_content = next(
        (msg.content for msg in reversed(lc_messages) if isinstance(msg, AIMessage)),
        "",
    )
    rag_query = (
        f"{user_content}\n{last_ai_content[:200]}" if last_ai_content else user_content
    )
    workspace_ids = [str(body.workspace_id)] if body.workspace_id else None
    rag_ctx = await build_rag_context(
        str(user.id), rag_query, openai_key, workspace_ids=workspace_ids
    )
    if rag_ctx:
        lc_messages = [
            lc_messages[0],
            SystemMessage(content=rag_ctx),
            *lc_messages[1:],
        ]

    logger.info(
        "chat_context_built",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )

    return ChatContext(
        lc_messages=lc_messages,
        conv_id=conv.id,
        human_msg_id=human_msg_id,
        user_content=user_content,
        is_consent=is_consent,
        approved=approved,
        is_first_exchange=is_first_exchange,
        parent_message_id=parent_message_id,
        workflow_dsl=conv.workflow_dsl,
        openai_key=openai_key,
        llm=llm,
    )
