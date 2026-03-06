import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.deps import ResolvedLLMConfig, get_current_user, get_llm_config
from app.core.config import settings
from app.core.security import resolve_api_key
from app.db.models import Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.plugins import plugin_registry
from app.rag.retriever import maybe_inject_rag_context
from app.services.memory_sync import sync_conversation_to_markdown

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

    if "approval" in chunk:
        pending = chunk["approval"]["pending_tool_call"]
        if pending is not None:
            events.append(
                _format_sse(
                    {
                        "type": "approval_required",
                        "tool": pending["name"],
                        "args": pending.get("args", {}),
                    }
                )
            )
    elif "llm" in chunk:
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


def _extract_token_counts(ai_msg: object | None) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from an AIMessage's usage_metadata."""
    if ai_msg is None:
        return 0, 0
    meta = getattr(ai_msg, "usage_metadata", None)
    if not meta:
        return 0, 0
    return meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0


def _build_expert_graph(
    route: str,
    *,
    provider: str,
    model: str,
    api_key: str,
    api_keys: list[str] | None,
    user_id: str,
    openai_api_key: str | None,
    tavily_api_key: str | None,
    enabled_tools: list[str] | None,
    mcp_tools: list,
    plugin_tools: list | None,
    conversation_id: str,
) -> CompiledStateGraph:
    """Return the appropriate compiled LangGraph for the given routing label.

    Expert agents (code/research/writing) each select a focused tool subset.
    Unknown labels fall back to the standard ReAct graph with all enabled tools.
    """
    from app.agent.experts import (
        create_code_agent_graph,
        create_research_agent_graph,
        create_writing_agent_graph,
    )

    if route == "code":
        return create_code_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
        )
    if route == "research":
        return create_research_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
        )
    if route == "writing":
        return create_writing_agent_graph(
            provider=provider,
            model=model,
            api_key=api_key,
            user_id=user_id,
            openai_api_key=openai_api_key,
            api_keys=api_keys,
            mcp_tools=mcp_tools,
            plugin_tools=plugin_tools,
            conversation_id=conversation_id,
        )
    # "simple" or any unknown label -> standard ReAct graph
    return create_graph(
        provider=provider,
        model=model,
        api_key=api_key,
        enabled_tools=enabled_tools,
        api_keys=api_keys,
        user_id=user_id,
        openai_api_key=openai_api_key,
        tavily_api_key=tavily_api_key,
        mcp_tools=mcp_tools,
        plugin_tools=plugin_tools,
        conversation_id=conversation_id,
    )


async def _load_tools(enabled_tools: list[str] | None) -> tuple[list, list | None]:
    """Load MCP and plugin tools based on the user's enabled_tools config."""
    mcp_tools: list = []
    if enabled_tools is None or "mcp" in enabled_tools:
        from app.tools.mcp_client import create_mcp_tools, parse_mcp_configs

        mcp_tools = await create_mcp_tools(parse_mcp_configs(settings.mcp_servers_json))

    plugin_tools: list | None = None
    if enabled_tools is None or "plugin" in enabled_tools:
        plugin_tools = plugin_registry.get_all_tools() or None

    return mcp_tools, plugin_tools


async def _save_response(
    conv_id: uuid.UUID,
    full_content: str,
    last_ai_msg: BaseMessage | None,
    llm: ResolvedLLMConfig,
) -> None:
    """Persist AI response to DB and trigger markdown sync."""
    if not full_content:
        return
    try:
        tokens_in, tokens_out = _extract_token_counts(last_ai_msg)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    Message(
                        conversation_id=conv_id,
                        role="ai",
                        content=full_content,
                        model_provider=llm.provider,
                        model_name=llm.model_name,
                        tokens_input=tokens_in,
                        tokens_output=tokens_out,
                    )
                )
        logger.info(
            "chat_stream_completed",
            conv_id=str(conv_id),
            response_chars=len(full_content),
        )
        asyncio.create_task(sync_conversation_to_markdown(conv_id))
    except Exception:
        logger.exception("failed_to_save_partial_response", conv_id=str(conv_id))


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(max_length=50000)


@router.post("/stream")
async def chat_stream(  # noqa: C901
    body: ChatRequest,
    user: User = Depends(get_current_user),
    llm: ResolvedLLMConfig = Depends(get_llm_config),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Check if this is a consent signal (HITL)
    is_consent = body.content.startswith("[CONSENT:")
    approved: bool | None = None
    if is_consent:
        approved = "ALLOW" in body.content

    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    # Don't save metadata messages to database
    if not is_consent:
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

    # Detect first exchange before RAG injection (counts only human messages)
    is_first_exchange = sum(1 for m in lc_messages if isinstance(m, HumanMessage)) == 1

    openai_key = resolve_api_key("openai", llm.raw_keys)
    # Build enriched query: current message + last AI reply for better recall
    last_ai_content = next(
        (msg.content for msg in reversed(lc_messages) if isinstance(msg, AIMessage)),
        "",
    )
    rag_query = (
        f"{body.content}\n{last_ai_content[:200]}" if last_ai_content else body.content
    )
    lc_messages = await maybe_inject_rag_context(
        lc_messages, rag_query, str(user.id), openai_key
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

    async def generate() -> AsyncGenerator[str]:  # noqa: C901
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
        mcp_tools, plugin_tools = await _load_tools(llm.enabled_tools)

        # Route classification — consent signals bypass routing
        route = "simple"
        if not is_consent:
            route = await classify_task(
                body.content,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
            )
            yield _format_sse({"type": "routing", "agent": route})
            logger.info("chat_routed", route=route, conv_id=str(conv_id))

        full_content = ""
        last_ai_msg = None
        stream_completed = False

        try:
            if route == "complex":
                # Supervisor pattern: non-streaming, runs plan→execute→aggregate
                supervisor = create_supervisor_graph(
                    provider=llm.provider,
                    model=llm.model_name,
                    api_key=llm.api_key,
                    api_keys=llm.api_keys,
                    user_id=str(user.id),
                    openai_api_key=openai_key,
                    tavily_api_key=tavily_key,
                    enabled_tools=llm.enabled_tools,
                )
                final_state = await supervisor.ainvoke(
                    SupervisorState(messages=lc_messages)
                )
                msgs = final_state.get("messages", [])
                if msgs:
                    last_ai_msg = msgs[-1]
                    full_content = str(getattr(last_ai_msg, "content", ""))
                    if full_content:
                        yield _format_sse(
                            {
                                "type": "delta",
                                "delta": full_content,
                                "content": full_content,
                            }
                        )
                stream_completed = True
            else:
                # Expert or standard ReAct — all use streaming AgentState graphs
                graph = _build_expert_graph(
                    route,
                    provider=llm.provider,
                    model=llm.model_name,
                    api_key=llm.api_key,
                    api_keys=llm.api_keys,
                    user_id=str(user.id),
                    openai_api_key=openai_key,
                    tavily_api_key=tavily_key,
                    enabled_tools=llm.enabled_tools,
                    mcp_tools=mcp_tools,
                    plugin_tools=plugin_tools,
                    conversation_id=str(conv_id),
                )
                state = AgentState(messages=lc_messages, approved=approved)
                async for chunk in graph.astream(state):
                    if "llm" in chunk:
                        last_ai_msg = chunk["llm"]["messages"][-1]
                    events, full_content = _sse_events_from_chunk(chunk, full_content)
                    for event in events:
                        yield event
            stream_completed = True
        except Exception:
            logger.exception("chat_stream_error", conv_id=str(conv_id))
            raise
        finally:
            new_title: str | None = None
            if full_content:
                try:
                    if stream_completed and is_first_exchange:
                        from app.agent.title_generator import generate_title

                        new_title = await generate_title(
                            user_message=body.content,
                            ai_reply=full_content,
                            provider=llm.provider,
                            model=llm.model_name,
                            api_key=llm.api_key,
                        )

                    tokens_in, tokens_out = _extract_token_counts(last_ai_msg)
                    async with AsyncSessionLocal() as session:
                        async with session.begin():
                            session.add(
                                Message(
                                    conversation_id=conv_id,
                                    role="ai",
                                    content=full_content,
                                    model_provider=llm.provider,
                                    model_name=llm.model_name,
                                    tokens_input=tokens_in,
                                    tokens_output=tokens_out,
                                )
                            )
                            if new_title:
                                await session.execute(
                                    update(Conversation)
                                    .where(Conversation.id == conv_id)
                                    .values(title=new_title)
                                )
                    logger.info(
                        "chat_stream_completed",
                        conv_id=str(conv_id),
                        response_chars=len(full_content),
                    )
                    asyncio.create_task(sync_conversation_to_markdown(conv_id))
                except Exception:
                    logger.exception(
                        "failed_to_save_partial_response",
                        conv_id=str(conv_id),
                    )
            if new_title:
                yield _format_sse({"type": "title_updated", "title": new_title})

    return StreamingResponse(generate(), media_type="text/event-stream")
