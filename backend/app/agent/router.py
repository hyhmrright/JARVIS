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

_CODE_KEYWORDS = frozenset(
    {
        "代码",
        "写代码",
        "debug",
        "调试",
        "实现",
        "function",
        "class",
        "脚本",
        "script",
        "程序",
        "编写",
        "bug",
        "报错",
        "error",
        "fix",
    }
)
_RESEARCH_KEYWORDS = frozenset(
    {
        "搜索",
        "查找",
        "调研",
        "research",
        "找一下",
        "查一下",
        "搜一下",
        "了解",
        "资料",
        "信息",
        "新闻",
        "文献",
        "论文",
    }
)
_WRITING_KEYWORDS = frozenset(
    {
        "写文章",
        "写一篇",
        "翻译",
        "总结",
        "润色",
        "修改文章",
        "起草",
        "文案",
        "copywriting",
        "draft",
        "summarize",
        "translate",
    }
)
_ACTION_WORDS = frozenset(
    {
        "写",
        "做",
        "帮",
        "创建",
        "生成",
        "分析",
        "解释",
        "write",
        "create",
        "build",
        "make",
        "analyze",
        "explain",
    }
)

# Ordered list: first match wins.
_KEYWORD_RULES: tuple[tuple[frozenset[str], str], ...] = (
    (_CODE_KEYWORDS, "code"),
    (_RESEARCH_KEYWORDS, "research"),
    (_WRITING_KEYWORDS, "writing"),
)


def _rule_based_classify(message: str) -> str | None:
    """Quick keyword-based classification. Returns None if no rule matches."""
    lower = message.lower()

    for keywords, label in _KEYWORD_RULES:
        if any(kw in lower for kw in keywords):
            return label

    if len(message) < 50 and not any(w in lower for w in _ACTION_WORDS):
        return "simple"
    return None


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
    # Fast path: rule-based classification (no LLM call)
    rule_result = _rule_based_classify(message)
    if rule_result is not None:
        logger.info("router_rule_classified", label=rule_result)
        return rule_result
    # Slow path: LLM fallback
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
