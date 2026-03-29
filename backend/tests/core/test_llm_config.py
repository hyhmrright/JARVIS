# backend/tests/core/test_llm_config.py
from app.core.llm_config import AgentConfig, ResolvedLLMConfig


def _make_llm() -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_key="sk-test",
        api_keys=["sk-test"],
        enabled_tools=None,
        persona_override=None,
        raw_keys={},
    )


def test_agent_config_defaults():
    llm = _make_llm()
    cfg = AgentConfig(llm=llm)
    assert cfg.user_id is None
    assert cfg.conversation_id is None
    assert cfg.depth == 0
    assert cfg.mcp_tools == []
    assert cfg.plugin_tools == []
    assert cfg.openai_api_key is None
    assert cfg.tavily_api_key is None
    assert cfg.workflow_dsl is None


def test_agent_config_full():
    llm = _make_llm()
    cfg = AgentConfig(
        llm=llm,
        user_id="u1",
        conversation_id="c1",
        depth=1,
        openai_api_key="sk-openai",
        tavily_api_key="tv-key",
    )
    assert cfg.user_id == "u1"
    assert cfg.depth == 1


def test_resolved_llm_config_re_exported_from_deps():
    """Existing callers that import from app.api.deps must still work."""
    from app.api.deps import ResolvedLLMConfig as DepsCopy

    assert DepsCopy is ResolvedLLMConfig
