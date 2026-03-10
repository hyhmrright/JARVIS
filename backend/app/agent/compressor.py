"""Context compression for long conversation histories.

When the accumulated message character count exceeds a configurable
threshold, older messages (excluding the system prompt and the most
recent *keep_recent* messages) are summarised into a single
``AIMessage`` by the same LLM backing the current conversation.
"""

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)

_SUMMARY_PROMPT = (
    "Summarise the following conversation history concisely. "
    "Preserve key facts, decisions, and context the user cares about. "
    "Reply with only the summary, no preamble."
)


async def compact_messages(
    messages: list[BaseMessage],
    *,
    provider: str,
    model: str,
    api_key: str,
    threshold: int = 50_000,
    keep_recent: int = 6,
    base_url: str | None = None,
) -> list[BaseMessage]:
    """Compress *messages* when total character count exceeds *threshold*.

    Returns the original list unchanged when compression is unnecessary.

    Layout of the returned list when compression fires::

        [system_msg, AIMessage(summary), ...last *keep_recent* messages]
    """
    total_chars = sum(len(str(m.content)) for m in messages)
    if total_chars < threshold:
        return messages

    # Separate system message (always first) from the rest.
    system_msgs: list[BaseMessage] = []
    rest: list[BaseMessage] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            system_msgs.append(m)
        else:
            rest.append(m)

    if len(rest) <= keep_recent:
        return messages

    to_compress = rest[:-keep_recent]
    to_keep = rest[-keep_recent:]

    summary_input = "\n".join(f"{m.type}: {m.content}" for m in to_compress)

    llm = get_llm(provider, model, api_key, base_url=base_url)
    summary_response = await llm.ainvoke(
        [
            SystemMessage(content=_SUMMARY_PROMPT),
            HumanMessage(content=summary_input),
        ]
    )

    summary_text = str(summary_response.content)
    logger.info(
        "context_compressed",
        original_count=len(messages),
        compressed_count=len(to_compress),
        summary_chars=len(summary_text),
    )

    return [
        *system_msgs,
        AIMessage(content=f"[Conversation summary]\n{summary_text}"),
        *to_keep,
    ]
