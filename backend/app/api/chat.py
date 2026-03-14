import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
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
from app.api.deps import get_current_user, get_llm_config
from app.core.config import settings
from app.core.limiter import limiter
from app.core.metrics import llm_requests_total
from app.core.sanitizer import sanitize_user_input
from app.core.security import resolve_api_key
from app.db.models import AgentSession, Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.plugins import plugin_registry
from app.rag.context import build_rag_context
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
    base_url: str | None = None,
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
            base_url=base_url,
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
            base_url=base_url,
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
            base_url=base_url,
        )
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
        base_url=base_url,
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


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(max_length=50000)
    workspace_id: uuid.UUID | None = None
    parent_message_id: uuid.UUID | None = None


@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(  # noqa: C901
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    user_content = sanitize_user_input(body.content)
    is_consent = user_content.startswith("[CONSENT:")
    approved: bool | None = None
    if is_consent:
        approved = "ALLOW" in user_content

    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    human_msg_id = None
    if not is_consent:
        human_msg = Message(
            conversation_id=conv.id,
            role="human",
            content=user_content,
            parent_id=body.parent_message_id,
        )
        db.add(human_msg)
        await db.commit()
        await db.refresh(human_msg)
        human_msg_id = human_msg.id

    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    all_conv_messages = history_rows.all()

    # Build tree
    msg_dict = {msg.id: msg for msg in all_conv_messages}
    all_history = []

    current_id = human_msg_id if not is_consent else body.parent_message_id
    # If this is the first message and parent_id is not provided, current_id might be None if consent?  # noqa: E501
    # Actually if consent, we rely on parent_message_id or just find the latest.
    if not current_id and all_conv_messages:
        # Fallback to the latest message if parent_id is missing
        current_id = all_conv_messages[-1].id

    while current_id and current_id in msg_dict:
        all_history.append(msg_dict[current_id])
        current_id = msg_dict[current_id].parent_id

    all_history.reverse()
    lc_messages = []
    for msg in all_history:
        message_class = _ROLE_TO_MESSAGE.get(msg.role)
        if message_class:
            lc_messages.append(message_class(content=msg.content))
        else:
            logger.debug(
                "chat_history_message_skipped",
                role=msg.role,
                msg_id=str(msg.id),
            )

    system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    # Detect first exchange (for auto title generation later)
    is_first_exchange = sum(1 for m in lc_messages if isinstance(m, HumanMessage)) == 1

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

    conv_id = conv.id

    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )

    tavily_key = settings.tavily_api_key

    async def generate() -> AsyncGenerator[str]:  # noqa: C901
        stream_error = False  # noqa: C901
        nonlocal lc_messages
        compressed_summary: str | None = None
        try:
            lc_messages = await compact_messages(
                lc_messages,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
            # Capture compressed context summary if compression occurred
            compressed_summary = next(
                (
                    getattr(m, "content", "")
                    for m in lc_messages
                    if getattr(m, "content", "").startswith("[Conversation summary]")
                ),
                None,
            )
        except Exception:
            logger.warning("context_compression_failed", exc_info=True)
        agent_session_id: uuid.UUID | None = None
        tools_used: list[str] = []
        try:
            async with AsyncSessionLocal() as _init_sess:
                async with _init_sess.begin():
                    ag_sess = AgentSession(
                        conversation_id=conv_id,
                        agent_type="main",
                        status="active",
                    )
                    _init_sess.add(ag_sess)
                    await _init_sess.flush()

        except Exception:
            logger.warning("agent_session_create_failed", exc_info=True)

        mcp_tools, plugin_tools = await _load_tools(llm.enabled_tools)

        route = "simple"
        if not is_consent:
            route = await classify_task(
                user_content,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
            yield _format_sse({"type": "routing", "agent": route})
            logger.info("chat_routed", route=route, conv_id=str(conv_id))

        full_content = ""
        last_ai_msg = None
        stream_completed = False

        is_disconnected = False

        try:
            if route == "complex":
                # Supervisor pattern: non-streaming, runs plan→execute→aggregate
                yield _format_sse({"type": "status", "message": "正在规划复杂任务..."})
                supervisor = create_supervisor_graph(
                    provider=llm.provider,
                    model=llm.model_name,
                    api_key=llm.api_key,
                    api_keys=llm.api_keys,
                    user_id=str(user.id),
                    openai_api_key=openai_key,
                    tavily_api_key=tavily_key,
                    enabled_tools=llm.enabled_tools,
                    base_url=llm.base_url,
                )
                tools_used = ["supervisor"]
                final_state = await supervisor.ainvoke(
                    SupervisorState(messages=lc_messages)
                )
                msgs = final_state.get("messages", [])
                if not msgs:
                    yield _format_sse({"type": "delta", "delta": "", "content": ""})
                else:
                    last_ai_msg = msgs[-1]
                    full_content = str(getattr(last_ai_msg, "content", ""))
                    if not full_content:
                        yield _format_sse({"type": "delta", "delta": "", "content": ""})
                    else:
                        # Chunk output every 50 chars for a streaming feel;
                        # yield control between pieces so ASGI flushes each frame.
                        chunk_size = 50
                        total = len(full_content)
                        for i in range(0, total, chunk_size):
                            piece = full_content[i : i + chunk_size]
                            is_last_chunk = i + chunk_size >= total
                            sse_event: dict = {"type": "delta", "delta": piece}
                            if is_last_chunk:
                                sse_event["content"] = full_content
                            yield _format_sse(sse_event)
                            if await request.is_disconnected():
                                is_disconnected = True
                                break
                            if not is_last_chunk:
                                await asyncio.sleep(0)
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
                    base_url=llm.base_url,
                )
                state = AgentState(messages=lc_messages, approved=approved)
                async for chunk in graph.astream(state):
                    if "llm" in chunk:
                        last_ai_msg = chunk["llm"]["messages"][-1]
                    if "tools" in chunk:
                        for tm in chunk["tools"]["messages"]:
                            if (
                                isinstance(tm, ToolMessage)
                                and tm.name
                                and (tm.name not in tools_used)
                            ):
                                tools_used.append(tm.name)
                    events, full_content = _sse_events_from_chunk(chunk, full_content)
                    for event in events:
                        yield event
                    if await request.is_disconnected():
                        is_disconnected = True
                        break
            stream_completed = not is_disconnected
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
                            user_message=user_content,
                            ai_reply=full_content,
                            provider=llm.provider,
                            model=llm.model_name,
                            api_key=llm.api_key,
                            base_url=llm.base_url,
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
                                    parent_id=human_msg_id
                                    if not is_consent
                                    else body.parent_message_id,  # noqa: E501
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
                    new_title = None  # Don't emit title_updated if DB write failed
                    logger.exception(
                        "failed_to_save_partial_response",
                        conv_id=str(conv_id),
                    )
            if agent_session_id:
                try:
                    session_status = "error" if stream_error else "completed"
                    tokens_meta_in, tokens_meta_out = _extract_token_counts(last_ai_msg)
                    metadata: dict = {
                        "model": llm.model_name,
                        "provider": llm.provider,
                        "tools_used": tools_used,
                        "input_tokens": tokens_meta_in or 0,
                        "output_tokens": tokens_meta_out or 0,
                        "trigger_type": "chat",
                    }
                    update_values: dict = {
                        "status": session_status,
                        "completed_at": datetime.now(UTC),
                        "metadata_json": metadata,
                    }
                    if compressed_summary:
                        update_values["context_summary"] = compressed_summary
                    async with AsyncSessionLocal() as status_sess:
                        async with status_sess.begin():
                            await status_sess.execute(
                                update(AgentSession)
                                .where(AgentSession.id == agent_session_id)
                                .values(**update_values)
                            )
                except Exception:
                    logger.warning("agent_session_update_failed", exc_info=True)
            llm_status = "error" if stream_error else "success"
            llm_requests_total.labels(
                provider=llm.provider, model=llm.model_name, status=llm_status
            ).inc()
            if new_title:
                yield _format_sse({"type": "title_updated", "title": new_title})

    return StreamingResponse(generate(), media_type="text/event-stream")


class RegenerateRequest(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    workspace_id: uuid.UUID | None = None


@router.post("/regenerate")
@limiter.limit("30/minute")
async def chat_regenerate(  # noqa: C901
    request: Request,
    body: RegenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)

    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    # The message we want to regenerate
    target_msg = await db.scalar(
        select(Message).where(
            Message.id == body.message_id, Message.conversation_id == conv.id
        )  # noqa: E501
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    all_conv_messages = history_rows.all()

    msg_dict = {msg.id: msg for msg in all_conv_messages}
    all_history = []

    # Trace back from target_msg parent (which should be the user message)
    current_id = target_msg.parent_id
    while current_id and current_id in msg_dict:
        all_history.append(msg_dict[current_id])
        current_id = msg_dict[current_id].parent_id

    all_history.reverse()

    lc_messages = []
    for msg in all_history:
        message_class = _ROLE_TO_MESSAGE.get(msg.role)
        if message_class:
            lc_messages.append(message_class(content=msg.content))

    system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    user_content = all_history[-1].content if all_history else ""
    openai_key = resolve_api_key("openai", llm.raw_keys)
    last_ai_content = next(
        (
            msg.content
            for msg in reversed(lc_messages[:-1])
            if isinstance(msg, AIMessage)
        ),  # noqa: E501
        "",
    )
    rag_query = (
        f"{user_content}\n{last_ai_content[:200]}" if last_ai_content else user_content
    )  # noqa: E501
    workspace_ids = [str(body.workspace_id)] if body.workspace_id else None
    rag_ctx = await build_rag_context(
        str(user.id), rag_query, openai_key, workspace_ids=workspace_ids
    )
    if rag_ctx:
        lc_messages = [lc_messages[0], SystemMessage(content=rag_ctx), *lc_messages[1:]]

    conv_id = conv.id
    tavily_key = settings.tavily_api_key

    async def generate() -> AsyncGenerator[str]:  # noqa: C901
        stream_error = False  # noqa: F841
        nonlocal lc_messages

        try:
            lc_messages = await compact_messages(
                lc_messages,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
        except Exception:
            pass

        try:
            async with AsyncSessionLocal() as _init_sess:
                async with _init_sess.begin():
                    ag_sess = AgentSession(
                        conversation_id=conv_id,
                        agent_type="main",
                        status="active",
                    )
                    _init_sess.add(ag_sess)
                    await _init_sess.flush()

        except Exception:
            pass

        mcp_tools, plugin_tools = await _load_tools(llm.enabled_tools)
        route = await classify_task(
            user_content,
            provider=llm.provider,
            model=llm.model_name,
            api_key=llm.api_key,
            base_url=llm.base_url,
        )
        yield _format_sse({"type": "routing", "agent": route})

        full_content = ""
        last_ai_msg = None

        try:
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
                base_url=llm.base_url,
            )
            state = AgentState(messages=lc_messages, approved=None)
            async for chunk in graph.astream(state):
                if "llm" in chunk:
                    last_ai_msg = chunk["llm"]["messages"][-1]
                events, full_content = _sse_events_from_chunk(chunk, full_content)
                for event in events:
                    yield event
        except Exception:
            raise
        finally:
            if full_content:
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
                                    parent_id=target_msg.parent_id,
                                )
                            )
                except Exception:
                    pass

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: str | None = None,
) -> None:
    await websocket.accept()
    if not token:
        await websocket.close(code=1008)
        return

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat":
                await websocket.send_json({"type": "token", "value": token})
            elif data.get("type") == "cancel":
                pass
    except WebSocketDisconnect:
        pass
