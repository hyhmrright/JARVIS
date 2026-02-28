import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.api.deps import ResolvedLLMConfig, get_current_user, get_llm_config
from app.core.config import settings
from app.core.security import resolve_api_key
from app.db.models import Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.rag.retriever import format_rag_context, retrieve_context

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_ROLE_TO_MESSAGE = {"human": HumanMessage, "ai": AIMessage}


def _format_sse(payload: dict) -> str:
    """Encode a dict as an SSE data line."""
    return "data: " + json.dumps(payload) + "\n\n"


def _sse_events_from_chunk(chunk: dict, full_content: str) -> tuple[list[str], str]:
    """Convert a LangGraph stream chunk into SSE event lines.

    Returns (list_of_sse_lines, updated_full_content).
    """
    events: list[str] = []

    if "llm" in chunk:
        ai_msg = chunk["llm"]["messages"][-1]
        # Emit tool_start events when the LLM decides to call tools
        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            for tc in ai_msg.tool_calls:
                events.append(
                    _format_sse(
                        {
                            "type": "tool_start",
                            "tool": tc["name"],
                            "args": tc.get("args", {}),
                        }
                    )
                )
        # Delta logic
        new_content = ai_msg.content
        delta = new_content[len(full_content) :]
        full_content = new_content
        if delta:
            events.append(
                _format_sse({"type": "delta", "delta": delta, "content": full_content})
            )
    elif "tools" in chunk:
        for tm in chunk["tools"]["messages"]:
            events.append(
                _format_sse(
                    {
                        "type": "tool_end",
                        "tool": tm.name,
                        "result_preview": tm.content[:200],
                    }
                )
            )

    return events, full_content


async def _maybe_inject_rag(
    messages: list[BaseMessage],
    query: str,
    user_id: str,
    openai_key: str | None,
) -> list[BaseMessage]:
    """Return messages with RAG context inserted at position 1, if available."""
    if not openai_key:
        return messages
    try:
        rag_chunks = await retrieve_context(query, user_id, openai_key)
        if rag_chunks:
            rag_msg = SystemMessage(content=format_rag_context(rag_chunks))
            logger.info(
                "rag_context_injected",
                user_id=user_id,
                chunk_count=len(rag_chunks),
            )
            return [messages[0], rag_msg, *messages[1:]]
    except Exception:
        logger.warning("rag_auto_inject_failed", exc_info=True)
    return messages


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(max_length=50000)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    llm: ResolvedLLMConfig = Depends(get_llm_config),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    db.add(Message(conversation_id=conv.id, role="human", content=body.content))
    await db.commit()

    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    lc_messages = [
        _ROLE_TO_MESSAGE[msg.role](content=msg.content)
        for msg in history_rows.all()
        if msg.role in _ROLE_TO_MESSAGE
    ]

    system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    openai_key = resolve_api_key("openai", llm.raw_keys)
    lc_messages = await _maybe_inject_rag(
        lc_messages, body.content, str(user.id), openai_key
    )

    conv_id = conv.id

    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )

    # Resolve Tavily API key for web search (server-level only)
    tavily_key = settings.tavily_api_key

    async def generate() -> AsyncGenerator[str]:
        nonlocal lc_messages
        try:
            lc_messages = await compact_messages(
                lc_messages,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
            )
        except Exception:
            logger.warning("context_compression_failed", exc_info=True)
        graph = create_graph(
            provider=llm.provider,
            model=llm.model_name,
            api_key=llm.api_key,
            enabled_tools=llm.enabled_tools,
            api_keys=llm.api_keys,
            user_id=str(user.id),
            openai_api_key=openai_key,
            tavily_api_key=tavily_key,
        )
        full_content = ""
        try:
            async for chunk in graph.astream(AgentState(messages=lc_messages)):
                events, full_content = _sse_events_from_chunk(chunk, full_content)
                for event in events:
                    yield event
        except Exception:
            logger.exception("chat_stream_error", conv_id=str(conv_id))
            raise
        finally:
            if full_content:
                try:
                    async with AsyncSessionLocal() as session:
                        async with session.begin():
                            session.add(
                                Message(
                                    conversation_id=conv_id,
                                    role="ai",
                                    content=full_content,
                                    model_provider=llm.provider,
                                    model_name=llm.model_name,
                                )
                            )
                    logger.info(
                        "chat_stream_completed",
                        conv_id=str(conv_id),
                        response_chars=len(full_content),
                    )
                except Exception:
                    logger.exception(
                        "failed_to_save_partial_response",
                        conv_id=str(conv_id),
                    )

    return StreamingResponse(generate(), media_type="text/event-stream")
