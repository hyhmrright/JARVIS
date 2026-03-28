"""FastAPI route handlers for the chat streaming API."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from dataclasses import replace as dc_replace
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.persona import build_system_prompt
from app.agent.router import classify_task
from app.agent.state import AgentState
from app.agent.supervisor import SupervisorState, create_supervisor_graph
from app.api.chat.graph_builder import (
    build_expert_graph,
    load_personal_plugin_tools,
    load_tools,
)
from app.api.chat.message_builder import (
    build_langchain_messages,
    build_memory_message,
    walk_message_chain,
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
from app.api.settings import PROVIDER_MODELS
from app.core.config import settings
from app.core.limiter import limiter
from app.core.metrics import llm_requests_total
from app.core.sanitizer import sanitize_user_input
from app.core.security import resolve_api_key
from app.db.models import AgentSession, Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.rag.context import build_rag_context
from app.services.memory_sync import sync_conversation_to_markdown

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
@limiter.limit("30/minute")
async def chat_stream(  # noqa: C901
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    if body.model_override:
        allowed = PROVIDER_MODELS.get(llm.provider, [])
        if allowed and body.model_override not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"model '{body.model_override}' not valid for '{llm.provider}'",
            )
        llm = dc_replace(llm, model_name=body.model_override)
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

    # Apply persona: conv.persona_id takes priority; body.persona_id only for new convs
    if not is_consent:
        from app.db.models import Persona

        if conv.persona_id:
            # Load persona to apply fields to inference config
            _persona = await db.scalar(
                select(Persona).where(Persona.id == conv.persona_id)
            )
            if _persona:
                if not conv.persona_override:
                    # Sync persona_override from FK once per conversation
                    conv.persona_override = _persona.system_prompt
                    await db.commit()
                # Apply persona fields to LLM config for this request
                if _persona.model_name:
                    llm = dc_replace(llm, model_name=_persona.model_name)
                if _persona.temperature is not None:
                    llm = dc_replace(llm, temperature=_persona.temperature)
                if _persona.enabled_tools is not None:
                    llm = dc_replace(llm, enabled_tools=_persona.enabled_tools)
        elif body.persona_id or body.workflow_dsl:
            # Lazy-check: only query message count when needed
            _msg_count = await db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conv.id)
            )
            if (_msg_count or 0) == 0:
                if body.persona_id:
                    _persona = await db.scalar(
                        select(Persona).where(
                            Persona.id == body.persona_id, Persona.user_id == user.id
                        )
                    )
                    if _persona:
                        conv.persona_override = _persona.system_prompt
                        await db.commit()
                if body.workflow_dsl:
                    conv.workflow_dsl = body.workflow_dsl
                    await db.commit()

    # Store workflow DSL if provided for a new conversation (when no persona path taken)
    elif body.workflow_dsl and not is_consent:
        _msg_count = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        if (_msg_count or 0) == 0:
            conv.workflow_dsl = body.workflow_dsl
            await db.commit()

    parent_message_id = body.parent_message_id or conv.active_leaf_id

    human_msg_id = None
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

    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    all_conv_messages = history_rows.all()

    # Build tree
    msg_dict = {msg.id: msg for msg in all_conv_messages}

    start_id = human_msg_id if not is_consent else parent_message_id
    # Fallback to the latest message if parent_id is missing
    if not start_id and all_conv_messages:
        start_id = all_conv_messages[-1].id

    all_history = walk_message_chain(msg_dict, start_id)
    lc_messages = build_langchain_messages(all_history)

    # 优先使用用户自定义的 system_prompt，否则使用 persona_override 构造
    if llm.system_prompt:
        system_msg = SystemMessage(content=llm.system_prompt)
    else:
        system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    # Inject persistent user memories after the main system prompt
    _mem_msg = await build_memory_message(db, user.id)
    if _mem_msg:
        lc_messages = [lc_messages[0], _mem_msg, *lc_messages[1:]]

    # Detect first exchange (for auto title generation later)
    is_first_exchange = sum(1 for m in lc_messages if isinstance(m, AIMessage)) == 0

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
        stream_error = False
        nonlocal lc_messages
        # Immediately notify the frontend of the persisted human message ID so
        # it can patch the optimistic message even if the stream is cancelled.
        if human_msg_id:
            yield format_sse(
                {"type": "human_msg_saved", "human_msg_id": str(human_msg_id)}
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

        (mcp_tools, plugin_tools), personal_tools = await asyncio.gather(
            load_tools(llm.enabled_tools),
            load_personal_plugin_tools(str(user.id)),
        )
        if personal_tools:
            plugin_tools = [*(plugin_tools or []), *personal_tools]

        route = "simple"
        if not is_consent:
            route = await classify_task(
                user_content,
                provider=llm.provider,
                model=llm.model_name,
                api_key=llm.api_key,
                base_url=llm.base_url,
            )
            yield format_sse({"type": "routing", "agent": route})
            logger.info("chat_routed", route=route, conv_id=str(conv_id))

        full_content = ""
        last_ai_msg = None
        stream_completed = False
        persisted_parent_id = human_msg_id if not is_consent else parent_message_id
        persisted_tool_batches: set[tuple[str, ...]] = set()
        persisted_tool_results: set[str] = set()

        is_disconnected = False

        try:
            if route == "complex":
                # Supervisor pattern: non-streaming, runs plan→execute→aggregate
                yield format_sse({"type": "status", "message": "正在规划复杂任务..."})
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
                    conversation_id=str(conv.id),
                    base_url=llm.base_url,
                    workflow_dsl=conv.workflow_dsl,
                    temperature=llm.temperature,
                    max_tokens=llm.max_tokens,
                )
                state = AgentState(messages=lc_messages, approved=approved)
                try:
                    async with asyncio.timeout(settings.graph_timeout_seconds):
                        async for chunk in graph.astream(state):
                            if "llm" in chunk:
                                last_ai_msg = chunk["llm"]["messages"][-1]
                                tool_calls = (
                                    getattr(last_ai_msg, "tool_calls", None) or []
                                )
                                signature = tool_call_signature(tool_calls)
                                if (
                                    tool_calls
                                    and signature not in persisted_tool_batches
                                ):
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
                                chunk, full_content, human_msg_id
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
            logger.exception("chat_stream_error", conv_id=str(conv_id))
            raise
        finally:
            new_title: str | None = None
            ai_msg_id: uuid.UUID | None = None
            tokens_in, tokens_out = extract_token_counts(last_ai_msg)
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

                    async with AsyncSessionLocal() as session:
                        async with session.begin():
                            saved_ai_msg = Message(
                                conversation_id=conv_id,
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
                            saved_conv = await session.get(Conversation, conv_id)
                            if saved_conv is not None:
                                saved_conv.active_leaf_id = ai_msg_id
                                if new_title:
                                    saved_conv.title = new_title
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
            if stream_completed and human_msg_id and ai_msg_id:
                yield format_sse(
                    {
                        "type": "done",
                        "human_msg_id": str(human_msg_id),
                        "ai_msg_id": str(ai_msg_id),
                        "model": llm.model_name,
                        "provider": llm.provider,
                        "input_tokens": tokens_in or 0,
                        "output_tokens": tokens_out or 0,
                    }
                )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/regenerate")
@limiter.limit("30/minute")
async def chat_regenerate(  # noqa: C901
    request: Request,
    body: RegenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    llm = await get_llm_config(user=user, db=db, workspace_id=body.workspace_id)
    if body.model_override:
        allowed = PROVIDER_MODELS.get(llm.provider, [])
        if allowed and body.model_override not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"model '{body.model_override}' not valid for '{llm.provider}'",
            )
        llm = dc_replace(llm, model_name=body.model_override)

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
        )
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
    # Trace back from target_msg's parent to reconstruct conversation history
    all_history = walk_message_chain(msg_dict, target_msg.parent_id)

    lc_messages = build_langchain_messages(all_history)

    # 优先使用用户自定义的 system_prompt，否则使用 persona_override 构造
    if llm.system_prompt:
        system_msg = SystemMessage(content=llm.system_prompt)
    else:
        system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    # Inject persistent user memories after the main system prompt
    _mem_msg = await build_memory_message(db, user.id)
    if _mem_msg:
        lc_messages = [lc_messages[0], _mem_msg, *lc_messages[1:]]

    user_content = all_history[-1].content if all_history else ""
    openai_key = resolve_api_key("openai", llm.raw_keys)
    last_ai_content = next(
        (
            msg.content
            for msg in reversed(lc_messages[:-1])
            if isinstance(msg, AIMessage)
        ),
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
        lc_messages = [lc_messages[0], SystemMessage(content=rag_ctx), *lc_messages[1:]]

    conv_id = conv.id
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

        (mcp_tools, plugin_tools), personal_tools = await asyncio.gather(
            load_tools(llm.enabled_tools),
            load_personal_plugin_tools(str(user.id)),
        )
        if personal_tools:
            plugin_tools = [*(plugin_tools or []), *personal_tools]

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
                conversation_id=str(conv.id),
                base_url=llm.base_url,
                workflow_dsl=conv.workflow_dsl,
                temperature=llm.temperature,
                max_tokens=llm.max_tokens,
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
