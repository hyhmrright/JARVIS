# GLM Support & Provider-Model Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ZhipuAI GLM model support and upgrade the settings UI to a provider-aware model selector (predefined list + custom option) for all providers.

**Architecture:** Backend adds a `case "zhipuai"` branch using `langchain-zhipuai` (MetaGLM official package) to the existing `match/case` LLM factory. Frontend replaces the free-text model input with a dynamic `<select>` that switches its option list based on the chosen provider, plus a "Custom…" escape hatch that reveals a text input.

**Tech Stack:** Python 3.13 / FastAPI / LangGraph / `langchain-zhipuai` / Vue 3 + TypeScript / Pinia / uv / bun

---

## Checklist

- [ ] Task 1: Add `langchain-zhipuai` dependency
- [ ] Task 2: Write failing unit tests for `get_llm()`
- [ ] Task 3: Implement `zhipuai` case in `llm.py` (make tests pass)
- [ ] Task 4: Add `zhipuai_api_key` to config and env template
- [ ] Task 5: Upgrade frontend to provider-model linked selector

---

## Task 1: Add `langchain-zhipuai` Dependency

**Files:**
- Modify: `backend/pyproject.toml` (dependencies section)

**Step 1: Install the package**

Run in `backend/` directory:
```bash
cd backend
uv add langchain-zhipuai
```

Expected: `langchain-zhipuai` appears in `backend/pyproject.toml` under `dependencies`, and `uv.lock` is updated.

**Step 2: Verify import works**

```bash
uv run python -c "from langchain_zhipuai import ChatZhipuAI; print('ok')"
```

Expected output: `ok`

**Step 3: Commit**

```bash
cd ..  # back to repo root
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add langchain-zhipuai dependency"
```

---

## Task 2: Write Failing Tests for `get_llm()`

**Files:**
- Create: `backend/tests/agent/test_llm.py`

**Step 1: Create the test file**

Create `backend/tests/agent/test_llm.py` with this exact content:

```python
from unittest.mock import MagicMock, patch

import pytest

from app.agent.llm import get_llm


def test_get_llm_deepseek_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatDeepSeek") as mock:
        get_llm("deepseek", "deepseek-chat", "key")
        mock.assert_called_once_with(model="deepseek-chat", api_key="key")


def test_get_llm_openai_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatOpenAI") as mock:
        get_llm("openai", "gpt-4o-mini", "key")
        mock.assert_called_once_with(model="gpt-4o-mini", api_key="key")


def test_get_llm_anthropic_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatAnthropic") as mock:
        get_llm("anthropic", "claude-3-5-haiku-20241022", "key")
        mock.assert_called_once_with(model="claude-3-5-haiku-20241022", api_key="key")


def test_get_llm_zhipuai_dispatches_correctly() -> None:
    with patch("app.agent.llm.ChatZhipuAI") as mock:
        get_llm("zhipuai", "glm-4-flash", "test-key")
        mock.assert_called_once_with(model="glm-4-flash", api_key="test-key")


def test_get_llm_zhipuai_model_variants() -> None:
    """Verify different GLM model strings are passed through unchanged."""
    for model in ("glm-4", "glm-4.7", "glm-4.7-FlashX", "glm-5", "glm-z1-flash"):
        with patch("app.agent.llm.ChatZhipuAI") as mock:
            get_llm("zhipuai", model, "key")
            mock.assert_called_once_with(model=model, api_key="key")


def test_get_llm_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown provider: fakeai"):
        get_llm("fakeai", "model", "key")
```

**Step 2: Run the tests to confirm they fail**

```bash
cd backend
uv run pytest tests/agent/test_llm.py -v
```

Expected: Several tests PASS (deepseek/openai/anthropic), `test_get_llm_zhipuai_*` tests FAIL with `ImportError` or `NameError` (ChatZhipuAI not imported yet), and `test_get_llm_unknown_provider_raises` PASSES.

If `test_get_llm_zhipuai_*` fail with "cannot import name 'ChatZhipuAI'" — that's correct. Proceed.

**Step 3: Commit the failing tests**

```bash
cd ..
git add backend/tests/agent/test_llm.py
git commit -m "test: add failing tests for get_llm() dispatch including zhipuai"
```

---

## Task 3: Implement `zhipuai` Case in `llm.py`

**Files:**
- Modify: `backend/app/agent/llm.py`

**Step 1: Read the current file**

Current content of `backend/app/agent/llm.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI


def get_llm(provider: str, model: str, api_key: str) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key)  # type: ignore[call-arg]
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown provider: {provider}")
```

**Step 2: Update `backend/app/agent/llm.py`**

Replace the entire file with:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_zhipuai import ChatZhipuAI


def get_llm(provider: str, model: str, api_key: str) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key)  # type: ignore[call-arg]
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case "zhipuai":
            return ChatZhipuAI(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown provider: {provider}")
```

**Step 3: Run the tests — all must pass**

```bash
cd backend
uv run pytest tests/agent/test_llm.py -v
```

Expected output:
```
tests/agent/test_llm.py::test_get_llm_deepseek_dispatches_correctly PASSED
tests/agent/test_llm.py::test_get_llm_openai_dispatches_correctly PASSED
tests/agent/test_llm.py::test_get_llm_anthropic_dispatches_correctly PASSED
tests/agent/test_llm.py::test_get_llm_zhipuai_dispatches_correctly PASSED
tests/agent/test_llm.py::test_get_llm_zhipuai_model_variants PASSED
tests/agent/test_llm.py::test_get_llm_unknown_provider_raises PASSED
```

If any test fails: re-read the error, fix `llm.py`, re-run.

**Step 4: Run mypy type check**

```bash
cd backend
uv run mypy app/agent/llm.py
```

Expected: `Success: no issues found` (or only pre-existing ignored issues). Fix any new errors before continuing.

**Step 5: Run full test suite to check for regressions**

```bash
cd backend
uv run pytest tests/ -v --ignore=tests/infra
```

Expected: All tests pass (infra tests are skipped — they require running Docker services).

**Step 6: Commit**

```bash
cd ..
git add backend/app/agent/llm.py
git commit -m "feat: add ZhipuAI GLM provider support to LLM factory"
```

---

## Task 4: Add `zhipuai_api_key` to Config and Env Template

**Files:**
- Modify: `backend/app/core/config.py` (line 18, after `anthropic_api_key`)
- Modify: `scripts/init-env.sh` (line 75, after `ANTHROPIC_API_KEY=`)

### 4a: Update `config.py`

**Step 1: Edit `backend/app/core/config.py`**

Current relevant section (lines 15–18):
```python
    # LLM API keys — optional, used as fallback when user has no stored key
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
```

Add one line after `anthropic_api_key`:
```python
    # LLM API keys — optional, used as fallback when user has no stored key
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    zhipuai_api_key: str = ""
```

**Step 2: Verify the config test still passes**

```bash
cd backend
uv run pytest tests/test_config.py -v
```

Expected: PASS. If it fails, check the error carefully — do not skip.

### 4b: Update `scripts/init-env.sh`

**Step 3: Edit `scripts/init-env.sh`**

Current relevant section (lines 72–75):
```bash
# LLM — fill in at least one key
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

Add one line after `ANTHROPIC_API_KEY=`:
```bash
# LLM — fill in at least one key
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
ZHIPUAI_API_KEY=
```

**Step 4: Commit both changes**

```bash
git add backend/app/core/config.py scripts/init-env.sh
git commit -m "feat: add zhipuai_api_key to config and env template"
```

---

## Task 5: Upgrade Frontend to Provider-Model Linked Selector

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`

### Context: How the current page works

The current `SettingsPage.vue` has:
- A `<select>` for `provider` with values: `deepseek`, `openai`, `anthropic`
- A plain `<input>` for `modelName`
- A password `<input>` for `apiKey`

The `save()` function sends `model_provider`, `model_name`, and optionally `api_keys`.

### Step 1: Replace `SettingsPage.vue`

Replace the entire file with this implementation:

```vue
<template>
  <div class="page-container">
    <div class="page-card animate-slide-up">
      <div class="page-header">
        <h2>{{ $t("settings.title") }}</h2>
        <router-link to="/" class="back-link">{{ $t("common.backToChat") }}</router-link>
      </div>
      <div class="shimmer-line animate-shimmer"></div>

      <form class="settings-form" @submit.prevent="save">
        <div class="form-group animate-slide-up-delay-1">
          <label for="provider">{{ $t("settings.provider") }}</label>
          <select id="provider" v-model="provider" @change="onProviderChange">
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="zhipuai">ZhipuAI (GLM)</option>
          </select>
        </div>

        <div class="form-group animate-slide-up-delay-2">
          <label for="modelSelect">{{ $t("settings.modelName") }}</label>
          <select id="modelSelect" v-model="modelSelect" @change="onModelSelectChange">
            <option v-for="m in currentProviderModels" :key="m" :value="m">{{ m }}</option>
            <option value="__custom__">{{ $t("settings.customModel") }}</option>
          </select>
          <input
            v-if="modelSelect === '__custom__'"
            id="modelName"
            v-model="customModelName"
            class="custom-model-input"
            :placeholder="$t('settings.customModelPlaceholder')"
            autocomplete="off"
          />
        </div>

        <div class="form-group animate-slide-up-delay-2">
          <label for="apiKey">{{ $t("settings.apiKey") }}</label>
          <input id="apiKey" v-model="apiKey" type="password" />
        </div>

        <div class="form-group animate-slide-up-delay-3">
          <label for="personaOverride">{{ $t("settings.personaOverride") }}</label>
          <textarea
            id="personaOverride"
            v-model="personaOverride"
            :placeholder="$t('settings.personaPlaceholder')"
            rows="4"
            maxlength="2000"
          />
        </div>

        <button type="submit" class="btn-primary animate-slide-up-delay-4">
          {{ $t("settings.save") }}
        </button>
      </form>

      <Transition name="toast">
        <div v-if="saved" class="toast-success">
          {{ $t("settings.saved") }}
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import client from "@/api/client";

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
};

const DEFAULT_MODEL: Record<string, string> = {
  deepseek: "deepseek-chat",
  openai: "gpt-4o-mini",
  anthropic: "claude-3-5-haiku-20241022",
  zhipuai: "glm-4-flash",
};

const provider = ref("deepseek");
const modelSelect = ref("deepseek-chat");
const customModelName = ref("");
const apiKey = ref("");
const personaOverride = ref("");
const saved = ref(false);

const currentProviderModels = computed(
  () => PROVIDER_MODELS[provider.value] ?? [],
);

/** The final model name sent to the API. */
const effectiveModelName = computed(() =>
  modelSelect.value === "__custom__" ? customModelName.value : modelSelect.value,
);

function onProviderChange() {
  const models = PROVIDER_MODELS[provider.value] ?? [];
  const defaultModel = DEFAULT_MODEL[provider.value] ?? models[0] ?? "";
  modelSelect.value = defaultModel;
  customModelName.value = "";
}

function onModelSelectChange() {
  // Nothing extra needed — template reactivity handles show/hide of custom input
}

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    personaOverride.value = data.persona_override ?? "";

    const savedModel: string = data.model_name ?? "";
    const models = PROVIDER_MODELS[provider.value] ?? [];
    if (models.includes(savedModel)) {
      modelSelect.value = savedModel;
    } else {
      modelSelect.value = "__custom__";
      customModelName.value = savedModel;
    }
  } catch {
    // Use defaults on error
  }
});

async function save() {
  const payload: Record<string, unknown> = {
    model_provider: provider.value,
    model_name: effectiveModelName.value,
    persona_override: personaOverride.value || null,
  };
  if (apiKey.value) {
    payload.api_keys = { [provider.value]: apiKey.value };
  }
  await client.put("/settings", payload);
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
}
</script>

<style scoped>
.page-card {
  max-width: 480px;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.custom-model-input {
  margin-top: var(--space-sm);
}

.toast-success {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--accent-a10);
  border: 1px solid var(--border-glow);
  border-radius: var(--radius-md);
  color: var(--accent);
  text-align: center;
  font-size: 14px;
}

.toast-enter-active {
  animation: slideUp 0.3s ease;
}

.toast-leave-active {
  animation: fadeIn 0.3s ease reverse;
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    animation: none;
  }
}
</style>
```

**Step 2: Add missing i18n keys**

The new template uses two new i18n keys: `settings.customModel` and `settings.customModelPlaceholder`. Add them to all locale files.

Check which locale files exist:
```bash
ls frontend/src/locales/
```

Expected: `zh.json en.json ja.json ko.json fr.json de.json`

Add to **each** locale file under the `"settings"` object. Use these translations:

**`zh.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "自定义...",
"customModelPlaceholder": "输入模型名称，例如 glm-4.7-FlashX"
```

**`en.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "Custom...",
"customModelPlaceholder": "Enter model name, e.g. glm-4.7-FlashX"
```

**`ja.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "カスタム...",
"customModelPlaceholder": "モデル名を入力（例：glm-4.7-FlashX）"
```

**`ko.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "직접 입력...",
"customModelPlaceholder": "모델 이름 입력 (예: glm-4.7-FlashX)"
```

**`fr.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "Personnalisé...",
"customModelPlaceholder": "Entrez le nom du modèle, ex: glm-4.7-FlashX"
```

**`de.json`** — add after `"personaPlaceholder"`:
```json
"customModel": "Benutzerdefiniert...",
"customModelPlaceholder": "Modellname eingeben, z.B. glm-4.7-FlashX"
```

To find the exact insertion point in each file, search for `"personaPlaceholder"` and add the two new keys after it.

**Step 3: Run frontend type check**

```bash
cd frontend
bun run type-check
```

Expected: No TypeScript errors. Fix any errors before continuing.

**Step 4: Run frontend lint**

```bash
bun run lint
```

Expected: No ESLint errors. If there are auto-fixable issues, run:
```bash
bun run lint:fix
```

**Step 5: Run frontend format check**

```bash
bun run format
```

Expected: Files formatted, no diff if already formatted.

**Step 6: Commit**

```bash
cd ..
git add frontend/src/pages/SettingsPage.vue frontend/src/locales/
git commit -m "feat: upgrade settings to provider-model linked selector with ZhipuAI support"
```

---

## Final Verification

**Step 1: Run the full backend test suite**

```bash
cd backend
uv run pytest tests/ -v --ignore=tests/infra
```

Expected: All tests pass.

**Step 2: Run all frontend checks**

```bash
cd frontend
bun run type-check && bun run lint
```

Expected: No errors.

**Step 3: Verify pre-commit hooks pass**

```bash
cd ..
pre-commit run --all-files
```

Expected: All hooks pass. If ruff/ESLint auto-fixes anything, stage those changes and commit:
```bash
git add -A
git commit -m "style: apply pre-commit auto-fixes"
```

---

## Summary of Commits

After all tasks, the branch should have these commits (in order):

1. `chore: add langchain-zhipuai dependency`
2. `test: add failing tests for get_llm() dispatch including zhipuai`
3. `feat: add ZhipuAI GLM provider support to LLM factory`
4. `feat: add zhipuai_api_key to config and env template`
5. `feat: upgrade settings to provider-model linked selector with ZhipuAI support`
6. *(optional)* `style: apply pre-commit auto-fixes`
