# CLAUDE.md — AI Agent Instructions / AI 编程助手指南

This file provides guidance to Claude Code when working in this repository.
本文件为 Claude Code 在此代码库中工作时提供指导。

## Branch Strategy / 分支策略

- **main**: Release only. Never commit or develop directly here. Only accepts merges from dev or other development branches.
- **dev**: Primary development branch (GitHub default). All daily development, bugfixes, and feature work go here or on sub-branches.
- After development is complete: dev → merge → main → push. No steps may be skipped.

- **main**：仅用于发版，不得直接提交或开发。只接受来自 dev 等开发分支的 merge。
- **dev**：主开发分支（GitHub 默认分支），所有日常开发、bugfix、功能开发均在此分支或其子分支进行。
- 开发完成后：dev → merge → main → push，不得跳过。

### Branch Naming / 协作分支命名规范

All feature branches are created from `dev`, named `<type>/<short-description>`:
所有功能分支从 `dev` 创建，命名格式 `<类型>/<简短描述>`：

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/rag-agent-integration` |
| `fix/` | Bug fixes | `fix/sse-disconnect` |
| `docs/` | Documentation only | `docs/api-reference` |
| `infra/` | Docker, CI, deployment | `infra/add-healthcheck` |

### Commit Message Format / Commit 消息规范

Follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>: <description>`

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：`<type>: <description>`

Types / 类型：`feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`、`ci`

## Worktree Parallel Development / Worktree 并行开发

### When to Use Worktrees / 何时使用 Worktree

- Developing multiple features simultaneously without interference
- Reviewing a PR without disrupting current work
- Emergency fix while the current branch has unfinished work

- 需要同时开发多个功能且互不干扰
- Review 他人 PR 时不想影响当前工作
- 紧急修复但当前分支有未完成的功能

### Creating and Managing Worktrees / 创建与管理

```bash
# Create worktree (branch off dev)
git worktree add .worktrees/<name> -b feature/<name> dev

# Initialize environment in worktree
cd .worktrees/<name>
cp ../../.env .                          # Copy environment variables
cd backend && uv sync && cd ..           # Install backend deps
cd frontend && bun install && cd ..      # Install frontend deps
cd backend && uv run alembic upgrade head && cd ..  # DB migration

# List all worktrees
git worktree list

# Remove worktree (after merge)
git worktree remove .worktrees/<name>

# Prune deleted worktree references
git worktree prune
```

### Using Worktrees in Claude Code / Claude Code 中使用 Worktree

```bash
# Launch isolated Claude Code session
claude --worktree feature-xxx

# Or request in conversation
> "在 worktree 中开发这个功能"
```

### Port Assignments / 端口分配

Docker base services (postgres/redis/qdrant/minio) are shared across all worktrees. Dev servers need different ports.
Docker 基础服务（postgres/redis/qdrant/minio）所有 worktree 共享。开发服务器需分配不同端口：

| Working Directory | Backend Port | Frontend Port |
|-------------------|-------------|---------------|
| Main (root) | 8000 | 3000 |
| Worktree 1 | 8001 | 3100 |
| Worktree 2 | 8002 | 3200 |

```bash
# Specify ports when starting in a worktree
uv run uvicorn app.main:app --reload --port 8001
bun run dev --port 3100
```

### Notes / 注意事项

- `.env` is not tracked by git; copy it manually when creating a new worktree.
- Avoid modifying `alembic/versions/` in multiple worktrees simultaneously (migration conflicts).
- `.worktrees/` is in `.gitignore` and will not be accidentally committed.
- The same branch cannot be checked out by two worktrees at the same time.

- `.env` 文件不在 git 中，新建 worktree 需手动复制。
- 避免多个 worktree 同时修改 `alembic/versions/`（数据库迁移冲突）。
- `.worktrees/` 已在 `.gitignore` 中，不会被意外提交。
- 同一分支不能被两个 worktree 同时检出。

## Project Overview / 项目概述

JARVIS is an AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations, using a monorepo structure.

**Completed features (Phase 1-12)**: RAG knowledge base, LangGraph ReAct agent tools (search/code_exec/datetime/file/shell/browser/rag), Gateway (Traefik), Cron jobs + trigger system (web/semantic/email watchers), Webhooks, Canvas rendering, Voice (TTS/STT), monitoring stack (Grafana/Loki/Prometheus), Plugin SDK, multi-agent supervisor, per-user rate limiting + input sanitization, audit log system, multi-tenant (Organizations / Workspaces / Invitations), Personal Access Tokens.

JARVIS 是具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台，采用 monorepo 结构。

**已完成功能（Phase 1-12）**：RAG 知识库、LangGraph ReAct agent 工具集（search/code_exec/datetime/file/shell/browser/rag）、Gateway（Traefik）、Cron 定时任务 + 触发器体系（web/semantic/email watcher）、Webhooks、Canvas 渲染、Voice（TTS/STT）、监控栈（Grafana/Loki/Prometheus）、Plugin SDK、多 agent supervisor、per-user 限速 + 输入过滤、审计日志、多租户（Organizations / Workspaces / Invitations）、Personal Access Tokens。

## Core Architecture / 核心架构

```
JARVIS/
├── backend/           # FastAPI backend (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # FastAPI entry point, lifespan manages infra connections
│   │   ├── agent/     # LangGraph ReAct agent (graph/llm/state/persona)
│   │   ├── api/       # HTTP routes (auth/chat/conversations/documents/settings/
│   │   │              #   cron/webhooks/voice/tts/canvas/organizations/workspaces/
│   │   │              #   invitations/plugins/keys/admin/logs/usage/gateway)
│   │   ├── channels/  # Multi-channel adapters (Slack/Discord/Telegram/Feishu/WhatsApp/webhook)
│   │   ├── core/      # Config, security (JWT/bcrypt/Fernet), rate limiting, audit log, metrics
│   │   ├── db/        # SQLAlchemy async models (18 tables) and sessions
│   │   ├── gateway/   # Agent runner, session manager, channel router, security
│   │   ├── infra/     # Infrastructure client singletons (Qdrant/MinIO/Redis)
│   │   ├── plugins/   # Plugin SDK loader
│   │   ├── rag/       # RAG pipeline (chunker/embedder/indexer/retriever/context)
│   │   ├── sandbox/   # Code execution sandbox manager
│   │   ├── scheduler/ # APScheduler + ARQ trigger system (runner/triggers/schemas)
│   │   ├── services/  # Shared services (memory_sync)
│   │   ├── tools/     # LangGraph tools (search/code_exec/datetime/file/shell/browser/rag)
│   │   └── worker.py  # ARQ worker (cron execution, webhook delivery, cleanup)
│   ├── alembic/       # Database migrations (017 versions)
│   └── tests/         # pytest test suite
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/       # Axios singleton + auth interceptor
│       ├── stores/    # Pinia stores (auth / chat / workspace)
│       ├── pages/     # Chat, Documents, Settings, Proactive, Plugins, Admin,
│       │              #   Usage, WorkspaceMembers, InviteAccept, Login, Register
│       ├── locales/   # i18n (zh/en/ja/ko/fr/de)
│       └── router/    # Vue Router + auth guard (11 routes)
├── database/          # Docker init scripts (postgres/redis/qdrant)
├── monitoring/        # Observability stack (Grafana/Loki/Prometheus configs)
├── docker-compose.yml # Full-stack orchestration
└── pyproject.toml     # Root dev tools config (ruff/pre-commit), no runtime deps
```

### Backend Architecture Highlights / 后端架构要点

**LLM Agent**: `agent/graph.py` implements a ReAct loop using LangGraph `StateGraph` (llm → tools → llm → END). A new graph instance is created per request with no checkpoint persistence. The LLM factory (`agent/llm.py`) dispatches via `match/case` to `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`.

**LLM Agent**：`agent/graph.py` 使用 LangGraph `StateGraph` 实现 ReAct 循环（llm → tools → llm → END）。每次请求创建新 graph 实例，不做 checkpoint 持久化。LLM 工厂（`agent/llm.py`）通过 `match/case` 分发到 `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`。

**Streaming Chat**: `api/chat.py`'s `POST /api/chat/stream` returns an SSE `StreamingResponse`. Note: the streaming generator uses a separate `AsyncSessionLocal` session internally (cannot reuse the request-level session as the request has already returned).

**流式对话**：`api/chat.py` 的 `POST /api/chat/stream` 返回 SSE `StreamingResponse`。注意：流式 generator 内部使用独立的 `AsyncSessionLocal` 会话（不能复用请求级会话，因为请求已返回）。

**RAG Pipeline**: Upload document → `extract_text()` → `chunk_text()` (sliding window, 500 words / 50-word overlap) → `OpenAIEmbeddings` (text-embedding-3-small, 1536 dims) → Qdrant upsert. One collection per user (`user_{id}`), one per workspace (`workspace_{id}`). RAG is exposed as an explicit agent tool (`tools/rag_tool.py`) and via `rag/context.py` for multi-collection search.

**RAG 管线**：上传文档 → `extract_text()` → `chunk_text()`（滑窗分词，500词/50词重叠）→ `OpenAIEmbeddings`（text-embedding-3-small，1536维）→ Qdrant upsert。每用户一个 collection（`user_{id}`），每 workspace 一个（`workspace_{id}`）。RAG 以 agent 工具形式暴露（`tools/rag_tool.py`），同时 `rag/context.py` 支持跨 collection 检索。

**Database Models**: 18 model classes — `users`, `user_settings` (Fernet-encrypted API keys), `conversations`, `agent_sessions`, `messages` (immutable), `documents` (soft delete), `cron_jobs`, `job_executions`, `webhooks`, `webhook_deliveries`, `plugin_configs`, `audit_logs`, `api_keys`, `organizations`, `workspaces`, `workspace_members`, `workspace_settings`, `invitations`. All use UUID primary keys.

**数据库模型**：18 个模型类 — `users`、`user_settings`（Fernet 加密 API keys）、`conversations`、`agent_sessions`、`messages`（不可变）、`documents`（软删除）、`cron_jobs`、`job_executions`、`webhooks`、`webhook_deliveries`、`plugin_configs`、`audit_logs`、`api_keys`、`organizations`、`workspaces`、`workspace_members`、`workspace_settings`、`invitations`。全部使用 UUID 主键。

**Infrastructure Singletons**: Qdrant uses lazy async init with `asyncio.Lock` (client + collection creation each have their own lock); MinIO uses `@lru_cache` + `asyncio.to_thread()` (sync SDK); PostgreSQL uses module-level engine + sessionmaker.

**基础设施单例**：Qdrant 用 lazy 异步初始化 + `asyncio.Lock`（客户端和 collection 创建各有独立锁）；MinIO 用 `@lru_cache` + `asyncio.to_thread()`（同步 SDK）；PostgreSQL 用模块级 engine + sessionmaker。

**Test Gotcha — asyncpg cross-event-loop contamination**: Each async test runs in its own event loop. Any code path that uses the module-level `AsyncSessionLocal` (e.g., `log_action`, `_resolve_pat`) will bind a connection to the current loop; the next test's loop cannot reuse it, causing `"Future attached to a different loop"`. Fix: add `autouse` fixtures in `conftest.py` that mock those call sites (see existing `_suppress_auth_audit_logging` and `_suppress_pat_last_used_update` fixtures).

**测试陷阱 — asyncpg 跨 event loop 连接池污染**：每个 async 测试有独立 event loop。使用模块级 `AsyncSessionLocal` 的代码路径（如 `log_action`、`_resolve_pat`）会将连接绑定到当前 loop；下一个测试的 loop 无法复用该连接，报 `"Future attached to a different loop"`。修复：在 `conftest.py` 中为这些调用点加 `autouse` mock（参考已有的 `_suppress_auth_audit_logging` 和 `_suppress_pat_last_used_update` fixture）。

### Frontend Architecture Highlights / 前端架构要点

**State Management**: Three Pinia stores — `auth.ts` (JWT token persisted to localStorage), `chat.ts` (conversation list + SSE streaming messages), `workspace.ts` (organization/workspace context). SSE uses native `fetch` + `ReadableStream` instead of Axios (Axios doesn't support streaming response bodies).

**状态管理**：三个 Pinia store — `auth.ts`（JWT token 持久化到 localStorage）、`chat.ts`（会话列表 + SSE 流式消息）、`workspace.ts`（组织/工作区上下文）。SSE 使用原生 `fetch` + `ReadableStream` 而非 Axios（Axios 不支持流式响应体）。

**Routing**: 11 routes, all page components are lazy-loaded. `beforeEach` guard checks `auth.isLoggedIn`; admin routes also check `requiresAdmin`.

**路由**：11 条路由，页面组件全部 lazy-loaded。`beforeEach` 守卫检查 `auth.isLoggedIn`；admin 路由还检查 `requiresAdmin`。

**API Client**: Axios instance with `baseURL: "/api"`, request interceptor reads token from localStorage, response interceptor handles 401 → auto logout. Dev server proxies `/api` → `http://localhost:8000` (Docker: `http://backend:8000`).

**API 客户端**：Axios 实例 `baseURL: "/api"`，请求拦截器从 localStorage 读取 token，响应拦截器处理 401 → 自动登出。dev server proxy `/api` → `http://localhost:8000`（Docker 内：`http://backend:8000`）。

**Internationalization**: vue-i18n, 6 languages, detection priority: localStorage → navigator.language → zh.

**国际化**：vue-i18n，6 种语言，检测优先级：localStorage → navigator.language → zh。

## Development Environment / 开发环境

- **Python**: 3.13 (`.python-version`) / **Python**：3.13（`.python-version`）
- **Package managers**: Backend `uv`, Frontend `bun` / **包管理器**：后端 `uv`，前端 `bun`
- **Virtual environment**: `.venv` (managed by uv automatically) / **虚拟环境**：`.venv`（uv 自动管理）

## Common Commands / 常用命令

### Environment Setup / 环境设置

```bash
bash scripts/init-env.sh             # First run: generates .env with random passwords/keys
uv sync                              # Install Python dependencies
cd frontend && bun install            # Install frontend dependencies
pre-commit install                    # Install git hooks
```

### Running the Application / 运行应用

```bash
# Start infrastructure only (for local dev) / 仅启动基础服务（本地开发用）
docker compose up -d postgres redis qdrant minio

# Backend (in backend/ directory) / 后端（在 backend/ 目录）
uv run alembic upgrade head           # Database migration / 数据库迁移
uv run uvicorn app.main:app --reload  # Dev server :8000

# Frontend (in frontend/ directory) / 前端（在 frontend/ 目录）
bun run dev                           # Dev server :3000 (proxies /api → backend:8000)

# Full-stack Docker (dev, with debug ports) / 全栈 Docker（开发模式，含调试端口）
docker compose up -d                  # App :80 · Backend :8000 · Grafana :3001 · Traefik dashboard :8080
docker compose ps                     # Verify all containers are healthy/running / 验证所有容器均 healthy/running

# Full-stack Docker (production, no debug ports) / 全栈 Docker（生产模式，无调试端口）
docker compose -f docker-compose.yml up -d  # App :80 · Grafana :3001 only
```

### Code Quality / 代码质量

```bash
# Backend / 后端
ruff check                   # Lint
ruff check --fix             # Lint + auto-fix
ruff format                  # Format
uv run mypy app              # Type check

# Frontend (in frontend/ directory) / 前端（在 frontend/ 目录）
bun run lint                 # ESLint
bun run lint:fix             # ESLint + auto-fix
bun run format               # Prettier
bun run type-check           # vue-tsc
```

### Testing / 测试

**Tests require `POSTGRES_PASSWORD` env var** (set automatically by `init-env.sh`) and a running `jarvis_test` database.
**测试需要 `POSTGRES_PASSWORD` 环境变量**（由 `init-env.sh` 自动设置），以及运行中的 `jarvis_test` 数据库。

**When local tests cannot run (e.g., missing database), read the test files manually before pushing.**
**本地无法运行测试时（如缺少数据库），推送前必须手动阅读相关测试文件。**

Rule: for every source file modified, read the corresponding test file(s) and verify:
规则：每修改一个源文件，就读对应的测试文件，确认：
1. All `patch()`/mock targets still exist in the modified code / 所有 patch 目标在修改后的代码中仍然存在
2. All error boundaries tested (OSError, None, ImportError, etc.) have matching handling in the implementation / 测试覆盖的错误边界在实现中有对应处理
3. All test assertions match the new behavior / 测试断言与新实现的行为一致

"lint/type-check passed" ≠ "tests will pass". Static analysis cannot catch wrong patch targets, missing exception handling, or incorrect filter logic.
"lint/type-check 通过" ≠ "测试会通过"。静态分析无法发现错误的 patch 目标、缺失的异常处理、不正确的过滤逻辑。

```bash
# Run in backend/ directory / 在 backend/ 目录执行
uv run pytest --collect-only -q          # Fast import check: catches runtime errors (e.g. response_model) that ruff/mypy miss / 快速 import 检查：发现 ruff/mypy 检测不到的运行时注册错误
uv run pytest tests/ -v                        # All tests / 所有测试
uv run pytest tests/api/test_auth.py -v        # Single file / 单个文件
uv run pytest tests/api/test_auth.py::test_login -v  # Single test case / 单个用例
```

### Pre-commit Hooks / Pre-commit Hooks

```bash
pre-commit run --all-files   # Manually run all hooks / 手动运行全部 hooks
```

Hooks include: YAML/TOML/JSON format checks, uv.lock sync, Ruff lint+format, ESLint, mypy, vue-tsc type check, gitleaks secret scanning, block direct commits to main.

Hooks 包含：YAML/TOML/JSON 格式检查、uv.lock 同步、Ruff lint+format、ESLint、mypy、vue-tsc 类型检查、gitleaks 密钥扫描、禁止直接提交 main。

### Dependency Management / 依赖管理

```bash
# Python (root pyproject.toml manages dev tools, backend/pyproject.toml manages runtime deps)
# Python（根目录 pyproject.toml 管开发工具，backend/pyproject.toml 管运行时依赖）
uv add <package>             # Add dependency (run in the appropriate directory)
uv add --group dev <package> # Add dev dependency
uv lock                      # Regenerate lock after manual pyproject.toml edits

# Frontend
cd frontend && bun add <package>
```

## Tool Configuration / 工具配置

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **mypy**: plugins=pydantic.mypy+sqlalchemy, disallow_untyped_defs=true, ignore_missing_imports=true
- **ESLint**: flat config, typescript-eslint + eslint-plugin-vue + prettier
- **TypeScript**: strict, bundler resolution, `@/*` → `src/*`

## Environment Variables / 环境变量

All sensitive configuration (database password, JWT secret, encryption key, MinIO credentials) has no default values and must be provided via `.env` or environment variables. Run `bash scripts/init-env.sh` to auto-generate. You only need to manually fill in `DEEPSEEK_API_KEY`.

所有敏感配置（数据库密码、JWT 密钥、加密密钥、MinIO 凭证）无默认值，必须通过 `.env` 或环境变量提供。运行 `bash scripts/init-env.sh` 自动生成。需手动填写 `DEEPSEEK_API_KEY`。

---

# Global Development Rules / 全局开发规则

## Pre-Git Operation Self-Check / Git 操作前自检

**Before every `git commit`, `git push`, or commit/push skill call, you must self-check:**
**每次执行 `git commit`、`git push` 或调用 commit/push skill 之前，必须自检：**

```
Were files modified in this session?
   → Yes → Has the quality loop (simplifier → commit → review) been fully completed?
            → No  → [STOP] Execute the quality loop immediately
            → Yes → Proceed with git operation
   → No  → Are there uncommitted changes in the working tree? (git diff / git diff --cached / git stash list)
            → Yes (including stash) → [STOP] Must complete the full quality loop first
            → No  → Proceed with git operation

本 session 是否修改过文件？
   → 是 → 质量循环（simplifier → commit → review）是否已完整通过？
           → 否 → 【STOP】立刻执行质量循环
           → 是 → 继续 git 操作
   → 否 → 工作区是否有未提交改动？（git diff / git diff --cached / git stash list）
           → 有（含 stash）→ 【STOP】必须先完整执行质量循环
           → 无 → 继续 git 操作
```

---

## Mandatory Code Change Workflow / 代码改动强制流程

### Tool Reference / 工具说明

| Tool | Type | Invocation | Model | Timing |
|------|------|-----------|-------|--------|
| simplify | Skill | `/simplify` | haiku (3 parallel agents) | Before commit |
| Pre-push code review | Task agent | `Task` tool, `subagent_type: "superpowers:code-reviewer"`, `model: "sonnet"` | **sonnet** | After commit, before push |
| PR code review | Skill | `Skill: code-review:code-review --comment` | session default | After push (optional, user request) |

### Trigger Conditions / 触发条件（满足任一即触发）

Any one of the following triggers the workflow:
满足任一即触发：

- Any file was modified using Edit / Write / NotebookEdit
- User intends to persist changes to Git or push to remote (including "sync", "upload", "create PR", "archive", "ship", etc.)
- About to invoke any commit / push related skill

- 使用 Edit / Write / NotebookEdit 修改了任何文件
- 用户意图将变更持久化到 Git 或推送到远程（含"同步"、"上传"、"发 PR"、"存档"、"ship"等表述）
- 准备调用任何 commit / push 相关 skill

### Execution Steps / 执行步骤（顺序固定，不可跳过）

```
Write code / Modify files
写代码 / 修改文件
      ↓
[REQUIRED] Run local static checks first (tools, not agents):
【必须】先本地执行静态检查（工具层面，非 agent）：
  cd backend && uv run ruff check --fix && uv run ruff format
  cd backend && uv run mypy app
      ↓
╔══════════════════ Quality Loop (repeat until no issues) ═════════════════╗
║ 质量循环（重复直到无问题）                                                ║
║                                                                          ║
║  A. [REQUIRED] Skill: /simplify                                          ║
║     【必须】Skill: /simplify                                              ║
║     (3 parallel agents: reuse / quality / efficiency, fixes in place)    ║
║     （3 个并发 agent：复用/质量/效率，直接修改文件）                      ║
║          ↓                                                               ║
║  B. git add + commit                                                     ║
║     First entry → git commit                                             ║
║     Re-entry after fix → git commit --amend (keep history clean pre-push)║
║     首次进入 → git commit                                                ║
║     修复后重入 → git commit --amend（未 push，保持历史干净）              ║
║          ↓                                                               ║
║  C. [REQUIRED] Task: superpowers:code-reviewer (model: "sonnet")         ║
║     【必须】Task: superpowers:code-reviewer（model: "sonnet"）            ║
║     (Provide BASE_SHA=HEAD~1, HEAD_SHA=HEAD                              ║
║      提供 BASE_SHA=HEAD~1, HEAD_SHA=HEAD)                                ║
║          ↓                                                               ║
║     Issues found? / 发现问题？                                           ║
║       Yes → Fix code ──────────────────────────→ Back to step A         ║
║       是  → 修复代码 ─────────────────────────→ 回到步骤 A              ║
║       No / 否 ↓                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
      ↓
git push (execute immediately, do not delay / 立即执行，不得停留)
```

**After pushing — only on explicit user request / 推送后，仅用户明确要求时：**

```
Skill: code-review:code-review --comment
```

**Key Notes / 关键说明：**
- The quality loop must be fully executed (A→B→C) and C must have no issues before exiting.
- Use `--amend` when re-entering the loop after fixes (keep a single commit before push).
- `--amend` is not a reason to skip review; C must still be re-executed.

- 质量循环必须完整执行（A→B→C）且 C 无问题才能退出。
- 修复后重入循环时用 `--amend`（未 push 前保持单一 commit）。
- `--amend` 不是跳过 review 的理由，仍需重新执行 C。

---

## Common Excuses for Skipping the Workflow (All Prohibited) / 禁止跳过流程的常见借口

The following reasons **must not** be used to skip the workflow:
以下理由均**不得**作为跳过依据：

| Excuse / 借口 | Correct Action / 正确做法 |
|--------------|--------------------------|
| "It's just a simple one-line change" / "只是简单的一行改动" | Must execute regardless of change size / 无论改动大小，必须执行 |
| "The user only said commit, not review" / "用户只说了 commit，没说要 review" | Commit itself is a trigger condition / commit 本身就是触发条件 |
| "I just reviewed similar code" / "刚才已经 review 过类似代码" | Must re-execute after every change / 每次改动后必须重新执行 |
| "This is a test file / docs, not core logic" / "这是测试文件/文档，不是核心逻辑" | Applies as long as Edit/Write was used / 只要用 Edit/Write 修改了文件就适用 |
| "Need to push before review" / "需要先 push 再 review" | Must review before push / 必须先 review 再 push |
| "The user is rushing, commit first" / "用户在催，先提交" | The workflow is not skipped due to urgency / 流程不因催促而跳过 |
| "I'm very familiar with this code" / "这段代码我很熟悉" | Familiarity does not affect requirements / 熟悉程度不影响流程要求 |
| "These changes weren't made in this session" / "这些改动不是本 session 做的" | Must execute as long as there are uncommitted changes / 只要有未提交改动，就必须执行 |
| "The user didn't use the word 'commit'" / "用户没用'commit'这个词" | Triggers as long as the intent is to commit/push / 只要意图是提交/推送，就触发 |
| "This is --amend, not a new commit" / "这是 --amend，不是新 commit" | --amend also modifies history, must execute / --amend 同样修改历史，必须执行 |
| "Changes are in stash, working tree is clean" / "改动在 stash 里，工作区是干净的" | Changes in stash also require the full workflow / stash 中的改动同样需要完整流程 |
| "The user only said commit, not push" / "用户只说了 commit，没说要 push" | Push must follow commit immediately / commit 后必须立即 push，无需额外指令 |
| "I'll push later" / "等会儿再 push" | Push is a required follow-up step, must not be delayed / push 是必要后续步骤，不得延迟 |
| "code-simplifier said it looks fine" / "code-simplifier 说没问题了" | Agents do semantic review, not ruff/mypy execution; local tool checks are mandatory / agent 做语义审查不执行工具，本地 ruff/mypy 不可省略 |

---

## Mandatory Checkpoints / 强制检查点

**Before executing `git push`**, confirm the quality loop has been fully completed:
**执行 git push 之前**，必须确认质量循环已完整通过：

| Step / 步骤 | Completion Indicator / 完成标志 |
|------------|-------------------------------|
| A. /simplify | Skill has run, 3-agent review complete, files fixed / Skill 已运行，三项审查完成，文件已修复 |
| B. git add + commit/amend | All changes (including simplifier modifications) committed / 所有改动（含 simplifier 修改）已提交 |
| C. superpowers:code-reviewer | Review found no issues, or all issues fixed in next iteration / review 无问题，或所有问题已在下一圈修复 |

The loop must be confirmed complete before the following tool calls:
以下工具调用前必须确认循环已完成：

- `Bash` executing `git push`
- `Skill` calling `commit-commands:*`
- `Skill` calling `pr-review-toolkit:*` (creating a PR / 创建 PR)

**After pushing / 推送后** (optional, only when user explicitly requests):
- `Skill` calling `code-review:code-review --comment`

**This rule applies to all projects, without exception.**
**此规则适用于所有项目，无一例外。**
