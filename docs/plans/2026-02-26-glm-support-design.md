# GLM Support & Provider-Model Selector Design

**Date:** 2026-02-26
**Branch:** `worktree-glm-support`
**Author:** Claude Code (brainstorming session)

## 1. Goal

Add ZhipuAI GLM series model support to JARVIS, and upgrade the frontend settings page from a plain model-name text input to a provider-aware model selector (predefined list + custom option) for all providers.

## 2. Scope

### Backend (4 files)

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `langchain-zhipuai>=0.2.0` dependency |
| `backend/app/agent/llm.py` | Add `case "zhipuai"` branch with `ChatZhipuAI` |
| `backend/app/core/config.py` | Add `zhipuai_api_key: str = ""` field |
| `scripts/init-env.sh` | Add `# ZHIPUAI_API_KEY=` comment placeholder |

### Frontend (1 file)

| File | Change |
|------|--------|
| `frontend/src/pages/SettingsPage.vue` | Provider+Model double-linked selector (see §4) |

### Tests (1 new file)

| File | Change |
|------|--------|
| `backend/tests/agent/test_llm.py` | Unit tests for `get_llm()` dispatch logic |

**No database migrations required** — no schema changes.
**No API route changes required** — backend accepts any `model_provider`/`model_name` string as before.

## 3. Backend Design

### 3.1 LangChain Integration

Use `langchain-zhipuai` (MetaGLM official package), consistent with the existing `match/case` dispatch pattern in `agent/llm.py`.

**Rationale over alternatives:**
- vs `langchain-community.ChatZhipuAI`: langchain-community is heavier, slower to add new GLM models
- vs OpenAI-compatible endpoint: depends on ZhipuAI compatibility layer stability

### 3.2 `agent/llm.py` Change

```python
from langchain_zhipuai import ChatZhipuAI  # new import

def get_llm(provider: str, model: str, api_key: str) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case "zhipuai":                                          # new
            return ChatZhipuAI(model=model, api_key=api_key)    # new
        case _:
            raise ValueError(f"Unknown provider: {provider}")
```

### 3.3 `config.py` Change

```python
# LLM API keys — optional, used as fallback when user has no stored key
deepseek_api_key: str = ""
openai_api_key: str = ""
anthropic_api_key: str = ""
zhipuai_api_key: str = ""   # new
```

`resolve_api_key()` in `security.py` uses `getattr(settings, f"{provider}_api_key", "")`, so no changes needed there — the new field is picked up automatically.

### 3.4 Environment Template

In `scripts/init-env.sh`, add alongside other LLM key comments:
```bash
# ZHIPUAI_API_KEY=your_zhipuai_key_here
```

## 4. Frontend Design

### 4.1 Model Selector UX (Industry Standard Pattern)

Replace the plain model-name text input with a provider-aware model selector:

```
[Provider Dropdown]          [Model Dropdown — changes per provider]
  ✔ DeepSeek                   ✔ deepseek-chat (default)
    OpenAI                       deepseek-reasoner
    Anthropic                   ─────────────────
    ZhipuAI (GLM)                Custom...  ← reveals text input
```

- Switching provider auto-selects that provider's default model
- Selecting "Custom..." reveals a text input for arbitrary model names
- This matches the UX pattern used by Cherry Studio, LobeChat, and Chatbox

### 4.2 Predefined Model Lists

```typescript
const PROVIDER_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
  anthropic: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
  zhipuai: [
    "glm-4-flash",
    "glm-4",
    "glm-4-plus",
    "glm-4.5",
    "glm-4.7",
    "glm-4.7-FlashX",
    "glm-5",
    "glm-z1-flash",
  ],
}

const DEFAULT_MODEL: Record<string, string> = {
  deepseek: "deepseek-chat",
  openai: "gpt-4o-mini",
  anthropic: "claude-3-5-haiku-20241022",
  zhipuai: "glm-4-flash",
}
```

### 4.3 Interaction Logic

```
onProviderChange(newProvider):
  if modelName is in old provider's list OR modelName == "custom":
    modelName = DEFAULT_MODEL[newProvider]
  // if user had typed a custom name, preserve it

onModelSelect(value):
  if value == "custom":
    show text input, focus it
  else:
    modelName = value, hide text input
```

The `<select>` for provider gains `<option value="zhipuai">ZhipuAI (GLM)</option>`.

## 5. Testing

### 5.1 New: `backend/tests/agent/test_llm.py`

```python
from unittest.mock import patch
import pytest
from app.agent.llm import get_llm

def test_get_llm_zhipuai():
    with patch("app.agent.llm.ChatZhipuAI") as mock:
        get_llm("zhipuai", "glm-4-flash", "test-key")
        mock.assert_called_once_with(model="glm-4-flash", api_key="test-key")

def test_get_llm_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_llm("fakeai", "model", "key")
```

## 6. What Does NOT Change

- Database schema and migrations
- API routes (`/api/chat/stream`, `/api/settings`)
- `security.py` `resolve_api_key()` — picks up `zhipuai_api_key` automatically
- `api/settings.py` default settings (remains `deepseek` / `deepseek-chat`)
- Existing tests

## 7. ZhipuAI Model Reference (2026-02)

| Model | Tier | Notes |
|-------|------|-------|
| `glm-4-flash` | Free | Recommended default |
| `glm-4` | Paid | Standard |
| `glm-4-plus` | Paid | High performance |
| `glm-4.5` | Paid | Agentic flagship (2025-07) |
| `glm-4.7` | Paid | Latest generation |
| `glm-4.7-FlashX` | Paid | Ultra-fast |
| `glm-5` | Paid | Top-tier |
| `glm-z1-flash` | Free | Reasoning model |
