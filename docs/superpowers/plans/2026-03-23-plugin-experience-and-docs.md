# Plugin Experience & Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the install→manage loop between SkillMarketPage and PluginsPage, then create five documentation files covering getting-started, plugins/skills, RAG, workflows, and the plugin SDK.

**Architecture:** Two independent work-streams. The frontend work adds ~60 lines spread across three existing files (PluginsPage.vue, SkillMarketPage.vue, and six locale files) — no new components required. The documentation work creates five Markdown files under `docs/user-guide/` and `docs/developer-guide/`, then updates README.md with links.

**Tech Stack:** Vue 3 / TypeScript / vue-i18n, existing `marketApi.listInstalled()` and `InstalledPluginOut` from `@/api/plugins`, Markdown.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/locales/en.json` | Modify | Add 4 i18n keys |
| `frontend/src/locales/zh.json` | Modify | Mirror i18n keys (Chinese) |
| `frontend/src/locales/ja.json` | Modify | Mirror i18n keys (Japanese) |
| `frontend/src/locales/ko.json` | Modify | Mirror i18n keys (Korean) |
| `frontend/src/locales/fr.json` | Modify | Mirror i18n keys (French) |
| `frontend/src/locales/de.json` | Modify | Mirror i18n keys (German) |
| `frontend/src/pages/PluginsPage.vue` | Modify | Add "Install from URL" button + modal wiring |
| `frontend/src/pages/SkillMarketPage.vue` | Modify | Add installed-state badges + refresh after install |
| `docs/user-guide/getting-started.md` | Create | Deploy-to-first-message walkthrough |
| `docs/user-guide/plugins-and-skills.md` | Create | Install/configure/uninstall guide |
| `docs/user-guide/rag-knowledge-base.md` | Create | RAG upload and query guide |
| `docs/user-guide/workflows.md` | Create | Workflow Studio walkthrough |
| `docs/developer-guide/plugin-sdk.md` | Create | Python plugin authoring guide |
| `README.md` | Modify | Add links to new docs |

---

### Task 1: i18n Keys (all 6 locale files)

**Files:**
- Modify: `frontend/src/locales/en.json:178-204` (plugins section)
- Modify: `frontend/src/locales/en.json:423-439` (skillMarket section)
- Modify: `frontend/src/locales/zh.json`, `ja.json`, `ko.json`, `fr.json`, `de.json`

Keys to add:
- `plugins.install` — label for a compact "Install" entry point (reserved for future use)
- `plugins.installFromUrl` — label for the header button that opens the install modal
- `skillMarket.installed` — green badge text for already-installed skills
- `skillMarket.alreadyInstalled` — disabled button label

- [ ] **Step 1: Add keys to `en.json`**

  In `plugins` object (after `"noDescription": "No description"` on line 203), add:
  ```json
  "install": "Install",
  "installFromUrl": "Install from URL"
  ```

  In `skillMarket` object (after `"installError": "Installation failed."` on line 438), add:
  ```json
  "installed": "Installed",
  "alreadyInstalled": "Installed ✓"
  ```

- [ ] **Step 2: Add keys to `zh.json`**

  In `plugins` section add:
  ```json
  "install": "安装",
  "installFromUrl": "从 URL 安装"
  ```
  In `skillMarket` section add:
  ```json
  "installed": "已安装",
  "alreadyInstalled": "已安装 ✓"
  ```

- [ ] **Step 3: Add keys to `ja.json`**

  In `plugins` section add:
  ```json
  "install": "インストール",
  "installFromUrl": "URLからインストール"
  ```
  In `skillMarket` section add:
  ```json
  "installed": "インストール済み",
  "alreadyInstalled": "インストール済み ✓"
  ```

- [ ] **Step 4: Add keys to `ko.json`**

  In `plugins` section add:
  ```json
  "install": "설치",
  "installFromUrl": "URL에서 설치"
  ```
  In `skillMarket` section add:
  ```json
  "installed": "설치됨",
  "alreadyInstalled": "설치됨 ✓"
  ```

- [ ] **Step 5: Add keys to `fr.json`**

  In `plugins` section add:
  ```json
  "install": "Installer",
  "installFromUrl": "Installer depuis une URL"
  ```
  In `skillMarket` section add:
  ```json
  "installed": "Installé",
  "alreadyInstalled": "Installé ✓"
  ```

- [ ] **Step 6: Add keys to `de.json`**

  In `plugins` section add:
  ```json
  "install": "Installieren",
  "installFromUrl": "Von URL installieren"
  ```
  In `skillMarket` section add:
  ```json
  "installed": "Installiert",
  "alreadyInstalled": "Installiert ✓"
  ```

- [ ] **Step 7: Verify with type-check**

  ```bash
  cd frontend && bun run type-check
  ```
  Expected: no errors.

- [ ] **Step 8: Commit**

  ```bash
  git add frontend/src/locales/
  git commit -m "feat: add i18n keys for plugin install UX"
  ```

---

### Task 2: PluginsPage — "Install from URL" Button

**Files:**
- Modify: `frontend/src/pages/PluginsPage.vue`

Context: The script (line 187) already imports `marketApi` and `InstalledPluginOut`. `loadInstalled()` (line 200-208) and `onMounted` (line 244-246, calls both `loadPlugins()` and `loadInstalled()`) already exist. Only the header button and modal are missing. `InstallFromUrlModal` is at `@/components/InstallFromUrlModal.vue` (confirmed used by SkillMarketPage).

- [ ] **Step 1: Add `InstallFromUrlModal` import and `showInstallModal` ref**

  After the existing imports in `<script setup>` (around line 189), add:
  ```ts
  import InstallFromUrlModal from "@/components/InstallFromUrlModal.vue";
  ```

  After the existing refs (after line 230, `const errorMsg = ref("")`), add:
  ```ts
  const showInstallModal = ref(false);
  ```

- [ ] **Step 2: Add "Install from URL" button in template header**

  In the `header-actions` div (lines 5-12), insert before the existing `<router-link to="/market"`:
  ```html
  <button class="install-btn" @click="showInstallModal = true">
    {{ t("plugins.installFromUrl") }}
  </button>
  ```

- [ ] **Step 3: Add modal to template**

  After the closing `</Teleport>` tag (line 180) but before `</div>` (line 181, the outermost div), add:
  ```html
  <InstallFromUrlModal
    v-if="showInstallModal"
    @close="showInstallModal = false"
    @installed="loadInstalled"
  />
  ```

- [ ] **Step 4: Run type-check and lint**

  ```bash
  cd frontend && bun run type-check && bun run lint:fix
  ```
  Expected: no errors.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/pages/PluginsPage.vue
  git commit -m "feat: add Install from URL button to PluginsPage header"
  ```

---

### Task 3: SkillMarketPage — Installed State Detection

**Files:**
- Modify: `frontend/src/pages/SkillMarketPage.vue`

Context: `marketApi.listInstalled()` returns `InstalledListResponse { system: InstalledPluginOut[], personal: InstalledPluginOut[] }`. `InstalledPluginOut` has `install_url: string`. `MarketSkillOut` also has `install_url: string`. Matching on `install_url` detects installed state. `InstalledPluginOut` is not currently imported in this file — it must be added.

- [ ] **Step 1: Add `InstalledPluginOut` to import**

  Line 174 currently reads:
  ```ts
  import type { MarketSkillOut } from "@/api/plugins";
  ```
  Change to:
  ```ts
  import type { MarketSkillOut, InstalledPluginOut } from "@/api/plugins";
  ```

- [ ] **Step 2: Add `installedUrls` ref and `loadInstalled` function**

  After line 189 (`const showInstallModal = ref(false);`), add:
  ```ts
  const installedUrls = ref(new Set<string>());

  async function loadInstalled() {
    try {
      const { data } = await marketApi.listInstalled();
      const urls = new Set<string>();
      for (const p of [...data.system, ...data.personal] as InstalledPluginOut[]) {
        if (p.install_url) urls.add(p.install_url);
      }
      installedUrls.value = urls;
    } catch {
      // Non-fatal: badges simply don't appear
    }
  }
  ```

- [ ] **Step 3: Update `onMounted` to also fetch installed list**

  Change line 252 from:
  ```ts
  onMounted(loadSkills);
  ```
  To:
  ```ts
  onMounted(() => {
    void Promise.all([loadSkills(), loadInstalled()]);
  });
  ```

- [ ] **Step 4: Refresh installed list after `installSkill` succeeds**

  In `installSkill()` (around line 237), after `toastSuccess(t("skillMarket.installSuccess", { name: skill.name }));`, add:
  ```ts
  await loadInstalled();
  ```

- [ ] **Step 5: Add `Check` to lucide imports**

  Line 171 imports `{ Zap, Search, Box, User, Download, ShieldAlert }`. Add `Check`:
  ```ts
  import { Zap, Search, Box, User, Download, ShieldAlert, Check } from "lucide-vue-next";
  ```

- [ ] **Step 6: Add installed badge and update install buttons in card template**

  Replace the install button block at lines 128-154 with:
  ```html
  <div class="mt-8 flex flex-col gap-2">
    <template v-if="installedUrls.has(skill.install_url)">
      <div
        class="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-900/40 py-2.5 text-xs font-black uppercase tracking-widest text-emerald-400"
      >
        <Check class="h-3.5 w-3.5" />
        {{ $t("skillMarket.installed") }}
      </div>
      <button
        disabled
        class="flex w-full items-center justify-center gap-2 rounded-xl bg-white/10 py-2.5 text-xs font-black uppercase tracking-widest text-zinc-500 cursor-not-allowed"
      >
        {{ $t("skillMarket.alreadyInstalled") }}
      </button>
    </template>
    <template v-else>
      <button
        :disabled="installingId === skill.id"
        class="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-2.5 text-xs font-black uppercase tracking-widest text-black transition-all hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
        @click="installSkill(skill, 'personal')"
      >
        <template v-if="installingId === skill.id">
          <div
            class="h-3 w-3 animate-spin rounded-full border-2 border-black/20 border-t-black"
          ></div>
          {{ $t("skillMarket.installing") }}
        </template>
        <template v-else>
          <Download class="h-3.5 w-3.5" />
          {{ $t("skillMarket.installPersonal") }}
        </template>
      </button>
      <button
        v-if="isAdmin && skill.scope.includes('system')"
        :disabled="installingId === skill.id"
        class="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-700 py-2.5 text-xs font-black uppercase tracking-widest text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
        @click="installSkill(skill, 'system')"
      >
        <Download class="h-3.5 w-3.5" />
        {{ $t("skillMarket.installSystem") }}
      </button>
    </template>
  </div>
  ```

- [ ] **Step 7: Run type-check and lint**

  ```bash
  cd frontend && bun run type-check && bun run lint:fix
  ```
  Expected: no errors.

- [ ] **Step 8: Commit**

  ```bash
  git add frontend/src/pages/SkillMarketPage.vue
  git commit -m "feat: show installed state badges on SkillMarketPage"
  ```

---

### Task 4: User Guide — Getting Started

**Files:**
- Create: `docs/user-guide/getting-started.md`

- [ ] **Step 1: Create the file**

  ```markdown
  # Getting Started with JARVIS

  This guide walks you from a fresh checkout to your first AI conversation in under ten minutes.

  **Prerequisites:**
  - Docker Desktop (or Docker Engine + Compose v2)
  - An OpenAI, DeepSeek, or Anthropic API key
  - Git

  ---

  ## 1. Clone and Configure

  ```bash
  git clone https://github.com/your-org/JARVIS.git
  cd JARVIS
  bash scripts/init-env.sh
  ```

  `init-env.sh` generates a `.env` file with random passwords and encryption keys. Open `.env` and fill in at least one API key:

  ```bash
  # .env — fill in one of these
  DEEPSEEK_API_KEY=sk-...
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=sk-ant-...
  ```

  ---

  ## 2. Start the Stack

  ```bash
  docker compose up -d
  ```

  Wait until all containers are healthy:

  ```bash
  docker compose ps
  # Every row should show "healthy" or "running"
  ```

  Open **http://localhost** in your browser.

  ---

  ## 3. Register and Log In

  1. Click **Register** on the login page.
  2. Enter an email and password (minimum 8 characters).
  3. You are automatically logged in after registration.

  ---

  ## 4. Configure Your LLM Provider

  1. Click your avatar (top-right) → **Settings**.
  2. Under **AI Model Config**, select your provider (DeepSeek / OpenAI / Anthropic / ZhipuAI / Ollama).
  3. Choose or enter a model name.
  4. In the **API Keys** section, paste your API key and click **Save**.

  JARVIS encrypts all API keys at rest using Fernet symmetric encryption.

  ---

  ## 5. Send Your First Message

  1. Click **New Conversation** in the sidebar.
  2. Type a message and press **Enter**.
  3. The assistant streams its reply token by token.

  **Try a tool call:** Ask "What time is it?" — JARVIS invokes the `datetime` tool and returns the current time.

  ---

  ## Next Steps

  - [Plugins & Skills](./plugins-and-skills.md) — extend your assistant with new capabilities
  - [RAG Knowledge Base](./rag-knowledge-base.md) — upload documents for context-aware answers
  - [Workflow Studio](./workflows.md) — automate multi-step tasks
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/user-guide/getting-started.md
  git commit -m "docs: add getting-started user guide"
  ```

---

### Task 5: User Guide — Plugins & Skills

**Files:**
- Create: `docs/user-guide/plugins-and-skills.md`

- [ ] **Step 1: Create the file**

  ```markdown
  # Plugins & Skills

  Plugins and skills extend JARVIS with new tools — from web search to custom API integrations.

  **Prerequisites:**
  - JARVIS running and logged in (see [Getting Started](./getting-started.md))

  ---

  ## Concepts

  | Term | What it is |
  |------|-----------|
  | **Plugin** | A local Python package loaded at startup from the file system |
  | **Skill** | An installable package pulled from the Skill Market or a custom URL |
  | **MCP server** | An external process exposing tools via the Model Context Protocol (stdio or HTTP) |

  Skills are the primary way to add capabilities at runtime without restarting JARVIS.

  ---

  ## Install from the Skill Market

  1. Navigate to **Plugins** → **Browse Market**.
  2. Browse or search the catalog.
  3. Click **Install (Personal)** to install for your account only, or **Install (System-wide)** (admin only) to make it available to all users.
  4. After installation the card shows a green **Installed** badge.

  ---

  ## Install from a URL

  Private or unlisted skills, `npx`-based MCP servers, and GitHub repositories can be installed directly:

  1. From the **Plugins** page, click **Install from URL** in the page header.
     _Alternatively, from the Skill Market header, click **+ Install from URL**._
  2. Paste the package URL or `npx` command.
  3. Choose **Personal** or **System-wide** scope.
  4. Click **Install**.

  **Example — install an npx MCP server:**
  ```
  npx -y @modelcontextprotocol/server-filesystem /home/user/docs
  ```

  ---

  ## Configure a Plugin

  Some plugins require API keys or other settings:

  1. Go to **Plugins** and find the plugin card.
  2. Click **Configure**.
  3. Enter key/value pairs. Toggle **Encrypt** for secrets (stored with Fernet encryption).
  4. Click **Add** for each entry.

  ---

  ## Enable / Disable Tools

  Each plugin exposes one or more tools. Individual tools can be toggled in the plugin configuration panel.

  ---

  ## Uninstall

  1. Go to **Plugins** → **My Installed Plugins** (or **System Installed Plugins** for admins).
  2. Click **Uninstall** next to the plugin.
  3. Confirm the dialog.

  The plugin is removed from the database; no restart is required for market-installed skills.

  ---

  ## Reload Locally-Loaded Plugins

  File-system plugins (Python packages in the `plugins/` directory) are loaded at startup. After adding or modifying a plugin file:

  1. Go to **Plugins**.
  2. Click **Reload Plugins**.

  This triggers a hot-reload without a full Docker restart.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/user-guide/plugins-and-skills.md
  git commit -m "docs: add plugins-and-skills user guide"
  ```

---

### Task 6: User Guide — RAG Knowledge Base

**Files:**
- Create: `docs/user-guide/rag-knowledge-base.md`

- [ ] **Step 1: Create the file**

  ```markdown
  # RAG Knowledge Base

  Upload documents so JARVIS can cite them when answering questions.

  **Prerequisites:**
  - JARVIS running, logged in, and an OpenAI API key configured in Settings (required for embeddings via `text-embedding-3-small`)

  ---

  ## Upload a Document

  1. Click **Documents** in the left sidebar.
  2. Click **Upload Document**.
  3. Select a file — supported formats: **PDF, TXT, MD, DOCX**.
  4. Wait for processing. JARVIS chunks the document (500 words / 50-word overlap) and indexes it in Qdrant using `text-embedding-3-small` (1536 dimensions).

  ---

  ## Ingest from a URL

  1. In the **Documents** panel, click **Add from URL**.
  2. Paste a public URL (HTML page, PDF link, etc.).
  3. JARVIS fetches, extracts, chunks, and indexes the content automatically.

  ---

  ## Ask a Question

  After uploading, start a new conversation and ask a question related to your documents:

  > "Summarize the key findings in my Q4 report."

  JARVIS performs a hybrid vector + keyword search, retrieves the top-5 matching chunks, and injects them as context before the LLM call. Sources are cited inline: `[1] "document-name"`.

  ---

  ## Workspace Collections

  Within a Workspace, all members share a common knowledge base:

  1. Go to **Workspace Settings** → **Documents**.
  2. Upload documents — they are stored in a shared `workspace_{id}` Qdrant collection.
  3. All members' conversations in that workspace automatically search both their personal collection and the workspace collection.

  Personal and workspace results are merged and re-ranked by combined score (70% vector, 30% keyword overlap) before being passed to the LLM.

  ---

  ## Remove a Document

  1. Go to **Documents**.
  2. Click the trash icon next to the document.
  3. The document and all its indexed chunks are deleted.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/user-guide/rag-knowledge-base.md
  git commit -m "docs: add rag-knowledge-base user guide"
  ```

---

### Task 7: User Guide — Workflow Studio

**Files:**
- Create: `docs/user-guide/workflows.md`

- [ ] **Step 1: Create the file**

  ```markdown
  # Workflow Studio

  Workflow Studio is a visual editor for building multi-step automation pipelines.

  **Prerequisites:**
  - JARVIS running and logged in (see [Getting Started](./getting-started.md))

  ---

  ## Open Workflow Studio

  Click **Workflows** in the left sidebar. The canvas loads with an empty graph.

  ---

  ## Create a Workflow

  1. Click **New Workflow**.
  2. Give it a name.
  3. The canvas shows a default **Start** node.

  ---

  ## Add Nodes

  1. Click **+ Add Node** (or right-click the canvas).
  2. Choose a node type:
     - **LLM** — call the configured language model
     - **Tool** — invoke an installed plugin tool
     - **HTTP** — make an outbound HTTP request
     - **Transform** — apply a JavaScript expression to the data
  3. Configure the node's parameters in the right panel.

  ---

  ## Connect Nodes

  Drag from an output port to an input port to create an edge. Data flows along edges as JSON objects.

  ---

  ## Run / Test

  1. Click **Run** in the toolbar.
  2. Provide test input in the **Input** panel on the left.
  3. Watch execution progress — each node highlights green (success) or red (error).
  4. Click any executed node to inspect its input and output.

  ---

  ## Save and Trigger from Chat

  1. Click **Save**.
  2. In a chat conversation, type `/run <workflow-name>` to trigger the workflow inline.
  3. The workflow result is streamed back as a chat message.

  Workflows can also be triggered on a schedule via the **Proactive Monitoring** page (cron syntax).
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/user-guide/workflows.md
  git commit -m "docs: add workflow-studio user guide"
  ```

---

### Task 8: Developer Guide — Plugin SDK

**Files:**
- Create: `docs/developer-guide/plugin-sdk.md`

Context: The real plugin system uses `JarvisPlugin` ABC and `PluginAPI` from `backend/app/plugins/sdk.py` and `backend/app/plugins/api.py`. Plugins subclass `JarvisPlugin`, set a `manifest = JarvisPluginManifest(...)` class attribute, and implement `async def on_load(self, api: PluginAPI)` where `api.register_tool(tool)` registers LangChain tools.

- [ ] **Step 1: Create the file**

  ```markdown
  # Plugin SDK

  Write a Python plugin to add custom tools to JARVIS.

  **Prerequisites:**
  - Python 3.11+
  - JARVIS running locally (see [Getting Started](../user-guide/getting-started.md))

  ---

  ## Directory Structure

  ```
  my_plugin/
  ├── __init__.py    # Exports the plugin class
  └── plugin.py      # Plugin implementation
  ```

  ---

  ## Minimal Example

  ```python
  # my_plugin/plugin.py
  from langchain_core.tools import tool

  from app.plugins.sdk import JarvisPlugin, JarvisPluginManifest, PluginCategory
  from app.plugins.api import PluginAPI


  class GreetPlugin(JarvisPlugin):
      manifest = JarvisPluginManifest(
          plugin_id="greet",
          name="Greet",
          version="1.0.0",
          description="Returns a greeting for the given name.",
          category=PluginCategory.TOOL,
          author="you@example.com",
      )

      async def on_load(self, api: PluginAPI) -> None:
          prefix = api.get_config("GREET_PREFIX") or "Hello"

          @tool
          def greet(name: str) -> str:
              """Return a greeting for the given name."""
              return f"{prefix}, {name}!"

          api.register_tool(greet)
  ```

  ```python
  # my_plugin/__init__.py
  from .plugin import GreetPlugin

  plugin = GreetPlugin()
  ```

  ---

  ## SDK API Reference

  ### `JarvisPlugin` (abstract base class)

  Subclass this and set a class-level `manifest`.

  | Method / property | Description |
  |-------------------|-------------|
  | `manifest` | Class attribute — a `JarvisPluginManifest` instance |
  | `async on_load(api)` | **Required.** Called once when the plugin is activated. Register tools here. |
  | `async on_unload()` | Optional. Called on app shutdown for cleanup. |
  | `plugin_id` | Property — returns `manifest.plugin_id` |

  ### `JarvisPluginManifest` fields

  | Field | Type | Description |
  |-------|------|-------------|
  | `plugin_id` | `str` | Unique slug (e.g. `"my-plugin"`) |
  | `name` | `str` | Human-readable name |
  | `version` | `str` | Semver string (default `"0.1.0"`) |
  | `description` | `str` | Brief purpose |
  | `category` | `PluginCategory` | One of: `TOOL`, `CHANNEL`, `RAG`, `AUTOMATION`, `UI`, `SYSTEM` |
  | `requires` | `list[str]` | IDs of dependency plugins |
  | `config_schema` | `dict` | JSON Schema for plugin config (optional) |

  ### `PluginAPI` methods

  | Method | Description |
  |--------|-------------|
  | `api.register_tool(tool)` | Register a LangChain `BaseTool` contributed by this plugin |
  | `api.register_channel(adapter)` | Register a channel adapter (Slack, Discord, etc.) |
  | `api.get_config(key, default=None)` | Read a value from environment variables |

  ### `SimpleSkillPlugin`

  For the common case of registering all public methods as tools automatically:

  ```python
  from app.plugins.sdk import SimpleSkillPlugin, JarvisPluginManifest


  class MathPlugin(SimpleSkillPlugin):
      manifest = JarvisPluginManifest(
          plugin_id="math",
          name="Math",
          description="Basic math operations.",
      )

      def add(self, a: float, b: float) -> str:
          """Add two numbers."""
          return str(a + b)

      def multiply(self, a: float, b: float) -> str:
          """Multiply two numbers."""
          return str(a * b)
  ```

  Each method becomes a tool named `{plugin_id}_{method_name}` with the docstring as description.

  ---

  ## Installing a Local Plugin

  1. Copy your plugin directory to `backend/plugins/my_plugin/`.
  2. In JARVIS, go to **Plugins** → **Reload Plugins**.
  3. The plugin appears in the list and its tools are available to the agent.

  ---

  ## Publishing to a Registry

  A registry is a JSON file served over HTTPS listing available skills:

  ```json
  [
    {
      "id": "greet",
      "name": "Greet",
      "version": "1.0.0",
      "description": "Returns a greeting for the given name.",
      "author": "you@example.com",
      "type": "python_plugin",
      "install_url": "https://your-host.com/plugins/greet.zip",
      "scope": ["personal", "system"]
    }
  ]
  ```

  Point JARVIS to your registry by setting `SKILL_REGISTRY_URL=https://your-host.com/registry.json` in `.env`.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/developer-guide/plugin-sdk.md
  git commit -m "docs: add plugin SDK developer guide"
  ```

---

### Task 9: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README to find where to insert docs section**

  Read `README.md` to locate the best insertion point (after features list, before or near the bottom).

- [ ] **Step 2: Add documentation links table**

  Insert in the appropriate location:
  ```markdown
  ## Documentation

  | Guide | Description |
  |-------|-------------|
  | [Getting Started](docs/user-guide/getting-started.md) | Deploy, first login, first conversation |
  | [Plugins & Skills](docs/user-guide/plugins-and-skills.md) | Browse, install, configure, and uninstall plugins |
  | [RAG Knowledge Base](docs/user-guide/rag-knowledge-base.md) | Upload documents, workspace collections, RAG queries |
  | [Workflow Studio](docs/user-guide/workflows.md) | Visual workflow editor, run from chat |
  | [Plugin SDK](docs/developer-guide/plugin-sdk.md) | Write and publish Python plugins |
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "docs: link to new user and developer guides from README"
  ```

---

## Verification Checklist

After all tasks are complete, confirm:

- [ ] PluginsPage header shows "Install from URL" button
- [ ] Clicking "Install from URL" opens the `InstallFromUrlModal`
- [ ] After install completes, installed section refreshes without page reload
- [ ] SkillMarketPage shows green "Installed" badge for already-installed skills on load
- [ ] SkillMarketPage immediately updates badge after installing a skill
- [ ] All 6 locale files contain `plugins.install`, `plugins.installFromUrl`, `skillMarket.installed`, `skillMarket.alreadyInstalled`
- [ ] `docs/user-guide/getting-started.md` exists and covers deploy-to-first-message
- [ ] `docs/user-guide/plugins-and-skills.md` exists and covers all install paths
- [ ] `docs/developer-guide/plugin-sdk.md` has a working minimal plugin example using `JarvisPlugin` + `PluginAPI`
- [ ] README links to all five new doc files
- [ ] `bun run type-check` passes
- [ ] `bun run lint:fix` passes with no remaining errors
