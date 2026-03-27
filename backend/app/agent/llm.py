"""LLM access for the agent layer.

Re-exports from ``app.core.llm_factory`` so existing agent-layer callers
(graph, supervisor, compressor, etc.) continue to work unchanged.
"""

from app.core.llm_factory import LLMInitError, get_llm, get_llm_with_fallback

__all__ = ["LLMInitError", "get_llm", "get_llm_with_fallback"]
