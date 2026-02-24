[中文](../../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

This file provides guidance for Claude Code when working in this codebase.

## Branch Strategy

- **main**: Used only for releases. Direct commits or development are not allowed. Only accepts merges from dev or other development branches.
- **dev**: Main development branch. All daily development, bugfixes, and feature work are done on this branch or its sub-branches.
- After development is complete: dev → merge → main → push. No steps may be skipped.

## Project Overview

JARVIS is an AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations, using a monorepo structure.

## Core Architecture

```
JARVIS/
├── backend/           # FastAPI backend (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # FastAPI entry point, lifespan manages infra connections
│   │   ├── agent/     # LangGraph ReAct agent (graph/llm/state)
│   │   ├── api/       # HTTP routes (auth/chat/conversations/documents/settings)
│   │   ├── core/      # Config (Pydantic Settings), security (JWT/bcrypt/Fernet), rate limiting
│   │   ├── db/        # SQLAlchemy async models and sessions
│   │   ├── infra/     # Infrastructure client singletons (Qdrant/MinIO/Redis)
│   │   ├── rag/       # RAG pipeline (chunker/embedder/indexer)
│   │   └── tools/     # LangGraph tools (search/code_exec/file/datetime)
│   ├── alembic/       # Database migrations
│   └── tests/         # pytest test suite
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/       # Axios singleton + auth interceptor
│       ├── stores/    # Pinia stores (auth + chat)
│       ├── pages/     # Page components (Login/Register/Chat/Documents/Settings)
│       ├── locales/   # i18n (zh/en/ja/ko/fr/de)
│       └── router/    # Vue Router + auth guard
├── database/          # Docker init scripts (postgres/redis/qdrant)
├── docker-compose.yml # Full-stack orchestration
└── pyproject.toml     # Root dev tools config (ruff/pyright/pre-commit), no runtime deps
```

### Backend Architecture Highlights

**LLM Agent**: `agent/graph.py` implements a ReAct loop using LangGraph `StateGraph` (llm → tools → llm → END). A new graph instance is created per request with no checkpoint persistence. The LLM factory (`agent/llm.py`) dispatches via `match/case` to `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`.

**Streaming Chat**: `api/chat.py`'s `POST /api/chat/stream` returns an SSE `StreamingResponse`. Note: the streaming generator uses a separate `AsyncSessionLocal` session internally (cannot reuse the request-level session as it closes when the handler returns).

**RAG Pipeline**: Upload document → `extract_text()` → `chunk_text()` (sliding window, 500 words/50 word overlap) → `OpenAIEmbeddings` (text-embedding-3-small, 1536 dims) → Qdrant upsert. One collection per user (`user_{id}`). Note: RAG retrieval is not yet wired into the agent conversation flow.

**Database Models**: 5 tables — `users`, `user_settings` (JSONB stores Fernet-encrypted API keys), `conversations`, `messages` (immutable), `documents` (soft delete). All use UUID primary keys.

**Infrastructure Singletons**: Qdrant uses module-level global + lazy init + asyncio.Lock; MinIO uses `@lru_cache` + `asyncio.to_thread()` (sync SDK); PostgreSQL uses module-level engine + sessionmaker.

### Frontend Architecture Highlights

**State Management**: Two Pinia stores — `auth.ts` (JWT token persisted to localStorage) and `chat.ts` (conversation list + SSE streaming messages). SSE uses native `fetch` + `ReadableStream` instead of Axios (Axios doesn't support streaming response bodies).

**Routing**: 5 routes, all page components are lazy-loaded. `beforeEach` guard checks `auth.isLoggedIn`.

**API Client**: Axios instance with `baseURL: "/api"`, request interceptor reads token from localStorage. Dev server proxies `/api` → `http://backend:8000`.

**Internationalization**: vue-i18n, 6 languages, detection priority: localStorage → navigator.language → zh.

## Development Environment

- **Python**: 3.13 (`.python-version`)
- **Package managers**: Backend `uv`, Frontend `bun`
- **Virtual environment**: `.venv` (managed by uv automatically)

## Common Commands

### Environment Setup
```bash
bash scripts/init-env.sh             # First run, generates .env (with random passwords/keys)
uv sync                              # Install Python dependencies
cd frontend && bun install            # Install frontend dependencies
pre-commit install                    # Install git hooks
```

### Running the Application
```bash
# Start infrastructure only (for local dev)
docker compose up -d postgres redis qdrant minio

# Backend (in backend/ directory)
uv run alembic upgrade head           # Database migration
uv run uvicorn app.main:app --reload  # Dev server :8000

# Frontend (in frontend/ directory)
bun run dev                           # Dev server :5173 (proxies /api → backend:8000)

# Full-stack Docker
docker compose up -d                  # Frontend :3000 · Backend :8000
```

### Code Quality
```bash
# Backend
ruff check                   # Lint
ruff check --fix             # Lint + auto-fix
ruff format                  # Format
pyright                      # Type check

# Frontend (in frontend/ directory)
bun run lint                 # ESLint
bun run lint:fix             # ESLint + auto-fix
bun run format               # Prettier
bun run type-check           # vue-tsc
```

### Testing
```bash
# Run in backend/ directory
uv run pytest tests/ -v                        # All tests
uv run pytest tests/api/test_auth.py -v        # Single file
uv run pytest tests/api/test_auth.py::test_login -v  # Single test case
```

### Pre-commit Hooks
```bash
pre-commit run --all-files   # Manually run all hooks
```

Hooks include: YAML/TOML/JSON format checks, uv.lock sync, Ruff lint+format, ESLint, Pyright, vue-tsc type check, gitleaks secret scanning, block direct commits to main.

### Dependency Management
```bash
# Python (root pyproject.toml manages dev tools, backend/pyproject.toml manages runtime deps)
uv add <package>             # Add dependency (run in the appropriate directory)
uv add --group dev <package> # Add dev dependency
uv lock                      # Regenerate lock after manual pyproject.toml edits

# Frontend
cd frontend && bun add <package>
```

## Tool Configuration

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **ESLint**: flat config, typescript-eslint + eslint-plugin-vue + prettier
- **TypeScript**: strict, bundler resolution, `@/*` → `src/*`

## Environment Variables

All sensitive configuration (database password, JWT secret, encryption key, MinIO credentials) has no default values and must be provided via `.env` or environment variables. Run `bash scripts/init-env.sh` to auto-generate. You only need to manually fill in `DEEPSEEK_API_KEY`.

---

# Global Development Rules

## Pre-Git Operation Self-Check

**Before every `git commit`, `git push`, or commit/push skill call, you must self-check:**

```
Were files modified in this session?
   → Yes → Has the quality loop (simplifier → commit → review) been fully completed?
            → No → [STOP] Execute the quality loop immediately
            → Yes → Proceed with git operation
   → No → Are there uncommitted changes in the working tree? (git diff / git diff --cached / git stash list)
            → Yes (including stash) → [STOP] Must complete the full quality loop first
            → No → Proceed with git operation
```

---

## Mandatory Code Change Workflow

### Tool Reference

| Tool | Type | Invocation | Timing |
|------|------|-----------|--------|
| code-simplifier | Task agent | `Task` tool, `subagent_type: "code-simplifier:code-simplifier"` | Before commit |
| Pre-push code review | Skill | `Skill: superpowers:requesting-code-review` | After commit, before push |
| PR code review | Skill | `Skill: code-review:code-review --comment` | After push (requires existing PR) |

### Trigger Conditions (any one triggers the workflow)

- Any file was modified using Edit / Write / NotebookEdit
- User intends to persist changes to Git or push to remote (including expressions like "sync", "upload", "create PR", "archive", "ship", etc.)
- About to invoke any commit / push related skill

### Execution Steps (fixed order, cannot be skipped)

```
Write code / Modify files
      ↓
╔══════════════════ Quality Loop (repeat until no issues) ═════════════════╗
║                                                                          ║
║  A. [REQUIRED] Task: code-simplifier                                     ║
║     (Task agent, directly modifies files)                                ║
║          ↓                                                               ║
║  B. git add + commit                                                     ║
║     First entry → git commit                                             ║
║     Re-entry after fix → git commit --amend (keep history clean pre-push)║
║          ↓                                                               ║
║  C. [REQUIRED] Skill: superpowers:requesting-code-review                 ║
║     (Provide BASE_SHA=HEAD~1, HEAD_SHA=HEAD)                             ║
║          ↓                                                               ║
║     Issues found?                                                        ║
║       Yes → Fix code ────────────────────────────→ Back to step A        ║
║       No  ↓                                                              ║
╚══════════════════════════════════════════════════════════════════════════╝
      ↓
git push (execute immediately, do not delay)
      ↓ (if a GitHub PR exists)
[REQUIRED] Skill: code-review:code-review --comment
```

**Key Notes:**
- The quality loop must be fully executed (A→B→C) and C must have no issues before exiting
- Use `--amend` when re-entering the loop after fixes (keep a single commit before push)
- `--amend` is not a reason to skip review; C must still be re-executed

---

## Common Excuses for Skipping the Workflow (All Prohibited)

The following reasons **must not** be used to skip the workflow:

| Excuse | Correct Action |
|--------|---------------|
| "It's just a simple one-line change" | Must be executed regardless of change size |
| "The user only said commit, not review" | Commit itself is a trigger condition |
| "I just reviewed similar code" | Must re-execute after every change |
| "This is a test file / docs, not core logic" | Applies as long as Edit/Write was used to modify files |
| "Need to push before review" | Must review before push |
| "The user is rushing, commit first" | The workflow is not skipped due to urgency |
| "I'm very familiar with this code" | Familiarity does not affect workflow requirements |
| "These changes weren't made in this session" | Must execute as long as there are uncommitted changes |
| "The user didn't use the word 'commit'" | Triggers as long as the intent is to commit/push |
| "This is --amend, not a new commit" | --amend also modifies history, must execute |
| "Changes are in stash, working tree is clean" | Changes in stash also require the full workflow |
| "The user only said commit, not push" | Push must follow commit immediately, no additional instruction needed |
| "I'll push later" | Push is a required follow-up step to commit, must not be delayed |

---

## Mandatory Checkpoints

**Before executing git push**, confirm the quality loop has been fully completed:

| Step | Completion Indicator |
|------|---------------------|
| A. code-simplifier | Task agent has run, files have been organized |
| B. git add + commit/amend | All changes (including simplifier modifications) have been committed |
| C. requesting-code-review | Review found no issues, or all issues were fixed in the next iteration |

The loop must be confirmed complete before the following tool calls:

- `Bash` executing `git push`
- `Skill` calling `commit-commands:*`
- `Skill` calling `pr-review-toolkit:*` (creating a PR)

**After pushing**, if a PR exists, also execute:
- `Skill` calling `code-review:code-review --comment`

**This rule applies to all projects, without exception.**
