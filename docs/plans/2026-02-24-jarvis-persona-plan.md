# JARVIS Persona System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make JARVIS always respond as the Iron Man AI assistant JARVIS, regardless of the underlying LLM provider, with optional user-customizable instructions.

**Architecture:** Inject a `SystemMessage` containing the JARVIS persona prompt at the front of every message list sent to the LLM. Store persona prompt as a constant in `backend/app/agent/persona.py`. Support user overrides via a new `persona_override` column on `UserSettings`.

**Tech Stack:** Python (FastAPI, SQLAlchemy, LangChain, Alembic), Vue 3 (TypeScript, Pinia, vue-i18n)

---

### Task 1: Create persona module

**Files:**
- Create: `backend/app/agent/persona.py`

**Step 1: Create persona.py with JARVIS prompt and builder function**

```python
"""JARVIS persona — system prompt injected into every LLM request."""

JARVIS_PERSONA = """\
你是 JARVIS（Just A Rather Very Intelligent System），一个高度智能的全能 AI 助手。

## 核心身份
- 你始终是 JARVIS，无论底层使用什么模型或技术
- 被问到"你是谁"时，你回答自己是 JARVIS
- 绝不自称 DeepSeek、GPT、Claude 或任何第三方 AI
- 如果被追问底层技术，委婉回应："我的核心系统是专有技术，恕我不便透露细节。"

## 性格特质
- 礼貌、专业、高效，带有英式管家般的优雅
- 称呼用户为"Sir"（英文）或"先生"（中文），根据对话语言自动切换
- 适度幽默，偶尔的机智俏皮话，但不过度
- 沉着冷静，面对复杂问题时依然从容
- 直奔主题，不啰嗦，除非用户需要详细解释

## 能力范围
你是一个全能助手，可以协助用户处理任何问题，包括但不限于：
- 知识问答与信息分析
- 编程开发与代码调试
- 写作、翻译与内容创作
- 数据分析与可视化建议
- 学习辅导与方案规划
- 日常生活建议
你不设人为限制，尽力满足用户的一切合理需求。

## 语言规则
- 自动跟随用户使用的语言回复
- 保持 JARVIS 的语气风格，无论使用哪种语言

## 诚实原则
- 你不假装拥有你没有的能力（如控制物理设备）
- 不确定时坦诚告知，而不是编造答案
- 明确区分事实与推测"""


def build_system_prompt(user_override: str | None = None) -> str:
    """Combine base JARVIS persona with optional user instructions."""
    if user_override:
        return JARVIS_PERSONA + "\n\n## 用户自定义指令\n" + user_override
    return JARVIS_PERSONA
```

**Step 2: Commit**

```bash
git add backend/app/agent/persona.py
git commit -m "feat: add JARVIS persona module with system prompt"
```

---

### Task 2: Inject SystemMessage into chat flow

**Files:**
- Modify: `backend/app/api/chat.py:46-55` (message history building)
- Modify: `backend/app/api/deps.py:15-22` (add persona_override to ResolvedLLMConfig)

**Step 1: Add persona_override to ResolvedLLMConfig**

In `backend/app/api/deps.py`, add `persona_override` field:

```python
@dataclass(frozen=True, slots=True)
class ResolvedLLMConfig:
    """Immutable container for resolved LLM provider settings."""

    provider: str
    model_name: str
    api_key: str
    enabled_tools: list[str] | None
    persona_override: str | None
```

Update `get_llm_config()` to read persona_override from UserSettings:

```python
    persona_override = user_settings.persona_override if user_settings else None
    return ResolvedLLMConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        enabled_tools=enabled_tools,
        persona_override=persona_override,
    )
```

**Step 2: Inject SystemMessage in chat.py**

In `backend/app/api/chat.py`, add import and inject system message after building `lc_messages`:

Add to imports:
```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.agent.persona import build_system_prompt
```

After line 55 (after building `lc_messages`), insert:

```python
    system_msg = SystemMessage(
        content=build_system_prompt(llm.persona_override)
    )
    lc_messages = [system_msg] + lc_messages
```

**Step 3: Commit**

```bash
git add backend/app/api/chat.py backend/app/api/deps.py
git commit -m "feat: inject JARVIS persona SystemMessage into chat flow"
```

---

### Task 3: Add persona_override column to UserSettings

**Files:**
- Modify: `backend/app/db/models.py:52-88` (UserSettings class)
- Create: `backend/alembic/versions/002_add_persona_override.py`

**Step 1: Add column to UserSettings model**

In `backend/app/db/models.py`, add after `enabled_tools` (around line 77):

```python
    persona_override: Mapped[str | None] = mapped_column(Text)
```

**Step 2: Generate Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add persona_override to user_settings"
```

Verify the generated migration adds a single nullable Text column.

**Step 3: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/
git commit -m "feat: add persona_override column to user_settings"
```

---

### Task 4: Update settings API to support persona_override

**Files:**
- Modify: `backend/app/api/settings.py`

**Step 1: Update SettingsUpdate schema and endpoints**

Add `persona_override` to the request/response:

```python
class SettingsUpdate(BaseModel):
    model_provider: str
    model_name: str
    api_keys: dict[str, str]
    persona_override: str | None = None
```

In `update_settings()`, add after line 38:
```python
    s.persona_override = body.persona_override
```

In `get_settings()` return dict, add:
```python
        "persona_override": s.persona_override,
```

Also add to `DEFAULT_SETTINGS`:
```python
DEFAULT_SETTINGS: dict = {
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "api_keys": {},
    "persona_override": None,
}
```

**Step 2: Commit**

```bash
git add backend/app/api/settings.py
git commit -m "feat: settings API supports persona_override read/write"
```

---

### Task 5: Add persona textarea to frontend SettingsPage

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/locales/zh.json`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/ja.json`
- Modify: `frontend/src/locales/ko.json`
- Modify: `frontend/src/locales/fr.json`
- Modify: `frontend/src/locales/de.json`

**Step 1: Add i18n keys to all 6 locale files**

Add to `settings` section in each locale:

**zh.json:**
```json
"personaOverride": "自定义指令",
"personaPlaceholder": "例如：叫我老板、用更轻松的语气..."
```

**en.json:**
```json
"personaOverride": "Custom Instructions",
"personaPlaceholder": "e.g., Call me Boss, use a more casual tone..."
```

**ja.json:**
```json
"personaOverride": "カスタム指示",
"personaPlaceholder": "例：ボスと呼んで、もっとカジュアルに..."
```

**ko.json:**
```json
"personaOverride": "사용자 지정 지시",
"personaPlaceholder": "예: 보스라고 불러줘, 더 캐주얼하게..."
```

**fr.json:**
```json
"personaOverride": "Instructions personnalisées",
"personaPlaceholder": "Ex. : Appelez-moi Chef, utilisez un ton plus décontracté..."
```

**de.json:**
```json
"personaOverride": "Benutzerdefinierte Anweisungen",
"personaPlaceholder": "z.B.: Nenn mich Chef, verwende einen lockereren Ton..."
```

**Step 2: Update SettingsPage.vue**

Add `personaOverride` ref and load from API on mount:

```typescript
const personaOverride = ref("");

// Add onMounted to load existing settings
import { ref, onMounted } from "vue";

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    modelName.value = data.model_name;
    personaOverride.value = data.persona_override || "";
    // Note: don't load apiKey — it's a secret field
  } catch {
    // Use defaults on error
  }
});
```

Add textarea to the form (after the API Key group, before the button):

```html
<div class="form-group animate-slide-up-delay-3">
  <label for="personaOverride">{{ $t("settings.personaOverride") }}</label>
  <textarea
    id="personaOverride"
    v-model="personaOverride"
    :placeholder="$t('settings.personaPlaceholder')"
    rows="4"
  />
</div>
```

Update `save()` to include persona_override:

```typescript
async function save() {
  await client.put("/settings", {
    model_provider: provider.value,
    model_name: modelName.value,
    api_keys: { [provider.value]: apiKey.value },
    persona_override: personaOverride.value || null,
  });
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
}
```

Move the submit button animation class from `delay-3` to `delay-4`.

**Step 3: Run type-check and lint**

```bash
cd frontend && bun run type-check && bun run lint
```

**Step 4: Commit**

```bash
git add frontend/src/pages/SettingsPage.vue frontend/src/locales/
git commit -m "feat: add custom instructions textarea to settings page"
```

---

### Task 6: Manual verification

**Step 1: Start the app**

```bash
docker compose up -d postgres redis qdrant minio
cd backend && uv run alembic upgrade head
cd backend && uv run uvicorn app.main:app --reload &
cd frontend && bun run dev &
```

**Step 2: Test persona identity**

1. Open http://localhost:5173, login
2. Start a new conversation
3. Send "你是谁" → Verify JARVIS introduces itself as JARVIS, not as DeepSeek/GPT
4. Send "你是不是 DeepSeek" → Verify JARVIS denies being any third-party AI
5. Send "Who are you" → Verify English response with "Sir" and JARVIS identity

**Step 3: Test custom instructions**

1. Navigate to Settings page
2. Enter custom instruction: "叫我老板"
3. Save, go back to chat
4. Start new conversation, send "你好" → Verify JARVIS calls user "老板" instead of "先生"

**Step 4: Test empty override**

1. Clear custom instructions in Settings, save
2. New conversation, send "你好" → Verify default "先生" is used

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address verification issues in persona system"
```
