"""Task router — classifies incoming messages to determine agent dispatch.

Returns one of: 'simple', 'complex', 'code', 'research', 'writing'
- simple: single-turn factual or conversational reply → ReAct Agent
- complex: multi-step task → Supervisor
- code: code generation/execution → CodeAgent
- research: research/search/knowledge retrieval → ResearchAgent
- writing: drafting/editing/summarizing documents → WritingAgent
"""

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm

logger = structlog.get_logger(__name__)

_VALID_LABELS = frozenset({"simple", "complex", "code", "research", "writing"})
_MAX_ROUTER_CHARS = 2000

_ROUTER_PROMPT = """\
Classify the user's message into exactly ONE of these categories:
- simple: short factual question, casual chat, or anything answerable in one step
- code: write/debug/explain code, build a script, technical implementation
- research: look up information, summarize sources, answer from documents
- writing: draft, edit, translate, or summarize text/documents
- complex: multi-step task that doesn't fit the above

Reply with ONLY the category word. Nothing else."""


async def classify_task(
    message: str,
    *,
    provider: str,
    model: str,
    api_key: str,
) -> str:
    """Classify a user message into an agent route.

    Returns one of: simple, complex, code, research, writing.
    Falls back to 'simple' on any error to avoid blocking the main chat flow.
    """
    try:
        llm = get_llm(provider, model, api_key)
        response = await llm.ainvoke(
            [
                SystemMessage(content=_ROUTER_PROMPT),
                HumanMessage(content=message[:_MAX_ROUTER_CHARS]),
            ]
        )
        content = response.content
        label = (content if isinstance(content, str) else "").strip().lower()
        if label in _VALID_LABELS:
            logger.info("router_classified", label=label)
            return label
        logger.warning("router_unknown_label", raw_label=label)
        return "simple"
    except Exception:
        logger.warning("router_classify_failed", exc_info=True)
        return "simple"
