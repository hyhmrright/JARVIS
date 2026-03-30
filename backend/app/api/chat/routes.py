"""FastAPI route handlers for the chat streaming API."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import ToolMessage
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.chat.context import ChatContext, build_chat_context
from app.api.chat.graph_builder import (
    build_expert_graph,
    load_all_tools,
)
from app.api.chat.schemas import ChatRequest, RegenerateRequest
from app.api.chat.sse import (
    extract_token_counts,
    format_sse,
    serialize_tool_message,
    sse_events_from_chunk,
    tool_call_signature,
)
from app.api.deps import get_current_user, get_llm_config
from app.core.config import settings
from app.core.limiter import limiter
from app.core.llm_config import AgentConfig, ResolvedLLMConfig
from app.core.metrics import llm_requests_total
from app.db.models import AgentSession, Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.services.memory_sync import sync_conversation_to_markdown

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _generate_stream(  # noqa: C901
    ctx: ChatContext,
    llm: ResolvedLLMConfig,
    request: Request,
    user_id_str: str,
) -> AsyncGenerator[str]:
    """Module-level SSE generator extracted from chat_stream."""
    stream_error = False
    lc_messages = ctx.lc_messages
    # Immediately notify the frontend of the persisted human message ID so
    # it can patch the optimistic message even if the stream is cancelled.
    if ctx.human_msg_id:
        yield format_sse(
            {"type": "human_msg_saved", "human_msg_id": str(ctx.human_msg_id)}
        )
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
        # SSE: per-chunk commit; no isolated_session()
        async with AsyncSessionLocal() as _init_sess:
            async with _init_sess.begin():
                ag_sess = AgentSession(
                    conversation_id=ctx.conv_id,
                    agent_type="main",
                    status="active",
                )
                _init_sess.add(ag_sess)
                await _init_sess.flush()
                agent_session_id = ag_sess.id

    except Exception:
        logger.warning("agent_session_create_failed", exc_info=True)

    mcp_tools, plugin_tools = await load_all_tools(user_id_str, llm.enabled_tools)

    route = "simple"
    if not ctx.is_consent:
        route = await classify_task(
            ctx.user_content,
            provider=llm.provider,
            model=llm.model_name,
            api_key=llm.api_key,
            base_url=llm.base_url,
        )
        yield format_sse({"type": "routing", "agent": route})
        logger.info("chat_routed", route=route, conv_id=str(ctx.conv_id))

    full_content = ""
    last_ai_msg = None
    stream_completed = False
    persisted_parent_id = (
        ctx.human_msg_id if not ctx.is_consent else ctx.parent_message_id
    )
    persisted_tool_batches: set[tuple[str, ...]] = set()
    persisted_tool_results: set[str] = set()

    is_disconnected = False

    tavily_key = settings.tavily_api_key

    try:
        if route == "complex":
            # Supervisor pattern: non-streaming, runs plan→execute→aggregate
            yield format_sse({"type": "status", "message": "正在规划复杂任务..."})
            supervisor = create_supervisor_graph(
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                api_keys=llm.api_keys,
                user_id=user_id_str,
                openai_api_key=ctx.openai_key,
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
                yield format_sse({"type": "delta", "delta": "", "content": ""})
            else:
                last_ai_msg = msgs[-1]
                full_content = str(getattr(last_ai_msg, "content", ""))
                if not full_content:
                    yield format_sse({"type": "delta", "delta": "", "content": ""})
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
                        yield format_sse(sse_event)
                        if await request.is_disconnected():
                            is_disconnected = True
                            break
                        if not is_last_chunk:
                            await asyncio.sleep(0)
        else:
            # Expert or standard ReAct — all use streaming AgentState graphs
            graph = build_expert_graph(
                route,
                AgentConfig(
                    llm=llm,
                    user_id=user_id_str,
                    conversation_id=str(ctx.conv_id),
                    openai_api_key=ctx.openai_key,
                    tavily_api_key=tavily_key,
                    mcp_tools=mcp_tools or [],
                    plugin_tools=plugin_tools or [],
                    workflow_dsl=ctx.workflow_dsl,
                ),
            )
            state = AgentState(messages=lc_messages, approved=ctx.approved)
            try:
                async with asyncio.timeout(settings.graph_timeout_seconds):
                    async for chunk in graph.astream(state):
                        if "llm" in chunk:
                            last_ai_msg = chunk["llm"]["messages"][-1]
                            tool_calls = getattr(last_ai_msg, "tool_calls", None) or []
                            signature = tool_call_signature(tool_calls)
                            if tool_calls and signature not in persisted_tool_batches:
                                # SSE: per-chunk commit; no isolated_session()
                                async with AsyncSessionLocal() as persist_sess:
                                    async with persist_sess.begin():
                                        persisted_ai = Message(
                                            conversation_id=ctx.conv_id,
                                            role="ai",
                                            content=str(
                                                getattr(last_ai_msg, "content", "")
                                            ),
                                            tool_calls=tool_calls,
                                            parent_id=persisted_parent_id,
                                        )
                                        persist_sess.add(persisted_ai)
                                        await persist_sess.flush()
                                        persisted_parent_id = persisted_ai.id
                                persisted_tool_batches.add(signature)
                        if "tools" in chunk:
                            for tm in chunk["tools"]["messages"]:
                                if (
                                    isinstance(tm, ToolMessage)
                                    and tm.name
                                    and (tm.name not in tools_used)
                                ):
                                    tools_used.append(tm.name)
                                if isinstance(tm, ToolMessage):
                                    tool_call_id = str(
                                        getattr(tm, "tool_call_id", None)
                                        or f"tool_{len(persisted_tool_results)}"
                                    )
                                    if tool_call_id in persisted_tool_results:
                                        continue
                                    # SSE: per-chunk commit; no isolated_session()
                                    async with AsyncSessionLocal() as persist_sess:
                                        async with persist_sess.begin():
                                            persisted_tool = Message(
                                                conversation_id=ctx.conv_id,
                                                role="tool",
                                                content=serialize_tool_message(tm),
                                                parent_id=persisted_parent_id,
                                            )
                                            persist_sess.add(persisted_tool)
                                            await persist_sess.flush()
                                            persisted_parent_id = persisted_tool.id
                                    persisted_tool_results.add(tool_call_id)
                        events, full_content = sse_events_from_chunk(
                            chunk, full_content, ctx.human_msg_id
                        )
                        for event in events:
                            yield event
                        if await request.is_disconnected():
                            is_disconnected = True
                            break
            except TimeoutError:
                yield (
                    "data: "
                    + json.dumps({"type": "error", "content": "Request timed out"})
                    + "\n\n"
                )
                return
        stream_completed = not is_disconnected
    except Exception:
        stream_error = True
        logger.exception("chat_stream_error", conv_id=str(ctx.conv_id))
        raise
    finally:
        new_title: str | None = None
        ai_msg_id: uuid.UUID | None = None
        tokens_in, tokens_out = extract_token_counts(last_ai_msg)
        if full_content:
            try:
                if stream_completed and ctx.is_first_exchange:
                    from app.agent.title_generator import generate_title

                    new_title = await generate_title(
                        user_message=ctx.user_content,
                        ai_reply=full_content,
                        provider=llm.provider,
                        model=llm.model_name,
                        api_key=llm.api_key,
                        base_url=llm.base_url,
                    )

                # SSE: per-chunk commit; no isolated_session()
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        saved_ai_msg = Message(
                            conversation_id=ctx.conv_id,
                            role="ai",
                            content=full_content,
                            model_provider=llm.provider,
                            model_name=llm.model_name,
                            tokens_input=tokens_in,
                            tokens_output=tokens_out,
                            parent_id=persisted_parent_id,
                        )
                        session.add(saved_ai_msg)
                        await session.flush()
                        ai_msg_id = saved_ai_msg.id
                        saved_conv = await session.get(Conversation, ctx.conv_id)
                        if saved_conv is not None:
                            saved_conv.active_leaf_id = ai_msg_id
                            if new_title:
                                saved_conv.title = new_title
                logger.info(
                    "chat_stream_completed",
                    conv_id=str(ctx.conv_id),
                    response_chars=len(full_content),
                )

                asyncio.create_task(sync_conversation_to_markdown(ctx.conv_id))
            except Exception:
                new_title = None  # Don't emit title_updated if DB write failed
                logger.exception(
                    "failed_to_save_partial_response",
                    conv_id=str(ctx.conv_id),
                )
        if agent_session_id:
            try:
                session_status = "error" if stream_error else "completed"
                metadata: dict = {
                    "model": llm.model_name,
                    "provider": llm.provider,
                    "tools_used": tools_used,
                    "input_tokens": tokens_in or 0,
                    "output_tokens": tokens_out or 0,
                    "trigger_type": "chat",
                }
                update_values: dict = {
                    "status": session_status,
                    "completed_at": datetime.now(UTC),
                    "metadata_json": metadata,
                }
                if compressed_summary:
                    update_values["context_summary"] = compressed_summary
                # SSE: per-chunk commit; no isolated_session()
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
            yield format_sse({"type": "title_updated", "title": new_title})
        if stream_completed and ctx.human_msg_id and ai_msg_id:
            yield format_sse(
                {
                    "type": "done",
                    "human_msg_id": str(ctx.human_msg_id),
                    "ai_msg_id": str(ai_msg_id),
                    "model": llm.model_name,
                    "provider": llm.provider,
                    "input_tokens": tokens_in or 0,
                    "output_tokens": tokens_out or 0,
                }
            )


@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    ctx = await build_chat_context(body, user, db, llm)
    llm = ctx.llm or llm  # build_chat_context may mutate llm (persona/override)
    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )
    return StreamingResponse(
        _generate_stream(ctx, llm, request, str(user.id)),
        media_type="text/event-stream",
    )


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

    target_msg = await db.scalar(
        select(Message).where(
            Message.id == body.message_id, Message.conversation_id == conv.id
        )
    )
    if not target_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Build context from history up to target_msg.parent_id (no new human msg).
    # content is a placeholder: _regen_parent_id overrides user_content from history.
    synthetic_req = ChatRequest(
        conversation_id=body.conversation_id,
        content=".",
        workspace_id=body.workspace_id,
        model_override=body.model_override,
    )
    ctx = await build_chat_context(
        synthetic_req, user, db, llm, _regen_parent_id=target_msg.parent_id
    )
    llm = ctx.llm or llm
    conv_id = ctx.conv_id
    user_content = ctx.user_content
    lc_messages = ctx.lc_messages
    openai_key = ctx.openai_key
    tavily_key = settings.tavily_api_key

    async def generate() -> AsyncGenerator[str]:  # noqa: C901
        nonlocal lc_messages
        persisted_parent_id = target_msg.parent_id
        persisted_tool_batches: set[tuple[str, ...]] = set()
        persisted_tool_results: set[str] = set()

        try:
            lc_messages = await compact_messages(
                lc_messages,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
        except Exception as exc:
            logger.warning("compact_messages_failed", error=str(exc))

        agent_session_id: uuid.UUID | None = None
        try:
            # SSE: per-chunk commit; no isolated_session()
            async with AsyncSessionLocal() as _init_sess:
                async with _init_sess.begin():
                    ag_sess = AgentSession(
                        conversation_id=conv_id,
                        agent_type="main",
                        status="active",
                    )
                    _init_sess.add(ag_sess)
                    await _init_sess.flush()
                    agent_session_id = ag_sess.id
        except Exception:
            logger.warning("agent_session_create_failed", exc_info=True)

        mcp_tools, plugin_tools = await load_all_tools(str(user.id), llm.enabled_tools)

        route = "main"
        try:
            route = await classify_task(
                user_content,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
        except Exception as e:
            logger.error("classify_task_failed_falling_back", error=str(e))

        yield format_sse({"type": "routing", "agent": route})
        full_content = ""
        last_ai_msg = None
        stream_error = False
        tools_used: list[str] = []

        try:
            graph = build_expert_graph(
                route,
                AgentConfig(
                    llm=llm,
                    user_id=str(user.id),
                    conversation_id=str(conv_id),
                    openai_api_key=openai_key,
                    tavily_api_key=tavily_key,
                    mcp_tools=mcp_tools or [],
                    plugin_tools=plugin_tools or [],
                    workflow_dsl=ctx.workflow_dsl,
                ),
            )
            state = AgentState(messages=lc_messages, approved=None)
            try:
                async with asyncio.timeout(settings.graph_timeout_seconds):
                    async for chunk in graph.astream(state):
                        if "llm" in chunk:
                            last_ai_msg = chunk["llm"]["messages"][-1]
                            tool_calls = getattr(last_ai_msg, "tool_calls", None) or []
                            signature = tool_call_signature(tool_calls)
                            if tool_calls and signature not in persisted_tool_batches:
                                # SSE: per-chunk commit; no isolated_session()
                                async with AsyncSessionLocal() as persist_sess:
                                    async with persist_sess.begin():
                                        persisted_ai = Message(
                                            conversation_id=conv_id,
                                            role="ai",
                                            content=str(
                                                getattr(last_ai_msg, "content", "")
                                            ),
                                            tool_calls=tool_calls,
                                            parent_id=persisted_parent_id,
                                        )
                                        persist_sess.add(persisted_ai)
                                        await persist_sess.flush()
                                        persisted_parent_id = persisted_ai.id
                                persisted_tool_batches.add(signature)
                        if "tools" in chunk:
                            for tm in chunk["tools"]["messages"]:
                                if (
                                    isinstance(tm, ToolMessage)
                                    and tm.name
                                    and tm.name not in tools_used
                                ):
                                    tools_used.append(tm.name)
                                if isinstance(tm, ToolMessage):
                                    tool_call_id = str(
                                        getattr(tm, "tool_call_id", None)
                                        or f"tool_{len(persisted_tool_results)}"
                                    )
                                    if tool_call_id in persisted_tool_results:
                                        continue
                                    # SSE: per-chunk commit; no isolated_session()
                                    async with AsyncSessionLocal() as persist_sess:
                                        async with persist_sess.begin():
                                            persisted_tool = Message(
                                                conversation_id=conv_id,
                                                role="tool",
                                                content=serialize_tool_message(tm),
                                                parent_id=persisted_parent_id,
                                            )
                                            persist_sess.add(persisted_tool)
                                            await persist_sess.flush()
                                            persisted_parent_id = persisted_tool.id
                                    persisted_tool_results.add(tool_call_id)
                        events, full_content = sse_events_from_chunk(
                            chunk, full_content
                        )
                        for event in events:
                            yield event
            except TimeoutError:
                yield (
                    "data: "
                    + json.dumps({"type": "error", "content": "Request timed out"})
                    + "\n\n"
                )
                return
        except Exception:
            stream_error = True
            raise
        finally:
            tokens_in, tokens_out = extract_token_counts(last_ai_msg)
            regen_ai_msg_id: uuid.UUID | None = None
            if full_content:
                try:
                    # SSE: per-chunk commit; no isolated_session()
                    async with AsyncSessionLocal() as session:
                        async with session.begin():
                            saved_regen_msg = Message(
                                conversation_id=conv_id,
                                role="ai",
                                content=full_content,
                                model_provider=llm.provider,
                                model_name=llm.model_name,
                                tokens_input=tokens_in,
                                tokens_output=tokens_out,
                                parent_id=persisted_parent_id,
                            )
                            session.add(saved_regen_msg)
                            await session.flush()
                            regen_ai_msg_id = saved_regen_msg.id
                            saved_conv = await session.get(Conversation, conv_id)
                            if saved_conv is not None:
                                saved_conv.active_leaf_id = regen_ai_msg_id
                except Exception:
                    logger.warning("regenerate_save_message_failed", exc_info=True)
            if agent_session_id:
                try:
                    # SSE: per-chunk commit; no isolated_session()
                    async with AsyncSessionLocal() as status_sess:
                        async with status_sess.begin():
                            await status_sess.execute(
                                update(AgentSession)
                                .where(AgentSession.id == agent_session_id)
                                .values(
                                    status="error" if stream_error else "completed",
                                    completed_at=datetime.now(UTC),
                                    metadata_json={
                                        "model": llm.model_name,
                                        "provider": llm.provider,
                                        "tools_used": tools_used,
                                        "input_tokens": tokens_in or 0,
                                        "output_tokens": tokens_out or 0,
                                        "trigger_type": "regenerate",
                                    },
                                )
                            )
                except Exception:
                    logger.warning("agent_session_update_failed", exc_info=True)
            if regen_ai_msg_id and not stream_error:
                yield format_sse(
                    {
                        "type": "done",
                        "ai_msg_id": str(regen_ai_msg_id),
                        "human_msg_id": str(target_msg.parent_id)
                        if target_msg.parent_id
                        else None,
                        "model": llm.model_name,
                        "provider": llm.provider,
                        "input_tokens": tokens_in or 0,
                        "output_tokens": tokens_out or 0,
                    }
                )

    return StreamingResponse(generate(), media_type="text/event-stream")
