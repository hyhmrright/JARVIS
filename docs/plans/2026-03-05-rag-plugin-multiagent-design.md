# JARVIS Phase B/A/C Design — RAG Integration, Plugin Enhancement, Multi-Agent Orchestration

**Date:** 2026-03-05
**Status:** Approved
**Implementation Strategy:** Parallel Worktrees, merge order B → A → C

---

## Overview

Three features to implement in parallel git worktrees:

| Priority | Feature | Worktree Branch |
|----------|---------|----------------|
| 1 (B) | RAG × Agent Integration | `feature/rag-agent-integration` |
| 2 (A) | Plugin System Enhancement | `feature/plugin-enhancement` |
| 3 (C) | Multi-Agent Orchestration | `feature/multi-agent` |

---

## Feature B: RAG × Agent Integration

### Architecture

```
User Message
    │
    ├─► [1] Auto Retrieval (rag/retriever.py)
    │       └─► Query Qdrant user_{id} collection
    │       └─► Top-K chunks → injected into system prompt tail
    │
    └─► [2] create_graph() — LangGraph ReAct
            ├─► LLM (with injected background context)
            ├─► Existing tools (search/code_exec/shell/browser...)
            └─► New: rag_search tool
                    └─► Active keyword re-query to Qdrant
```

### File Changes

| File | Change |
|------|--------|
| `backend/app/rag/retriever.py` | **New**: Qdrant semantic retrieval, returns top-K chunks |
| `backend/app/tools/rag_tool.py` | **New**: LangGraph tool wrapping retriever |
| `backend/app/api/chat.py` | Modify: auto-retrieve before conversation, append to system prompt |
| `backend/app/agent/graph.py` | Modify: inject `rag_search` tool into tool chain |

### Key Design Decisions

- **Auto injection**: Retrieve Top-5 chunks; truncate if exceeding 2000 tokens; mark with `[知识库参考]` separator
- **Tool retrieval**: `rag_search(query: str, top_k: int = 3)` as standalone LangGraph tool
- **Empty collection fallback**: When user has no documents, both auto-injection and tool silently skip — no errors
- **Worktree**: `feature/rag-agent-integration`, branch from `dev`

---

## Feature A: Plugin System Enhancement

### Bug Fixes (3 items)

| Bug | File | Fix |
|-----|------|-----|
| `sys.modules` ghost entry | `plugins/loader.py` | `sys.modules.pop(namespaced, None)` in except block after failed `exec_module` |
| `_run_agent` silent failure | `gateway/agent_runner.py` | try/except, return user-friendly error message on exception |
| Plugin tools not pre-filtered | `api/chat.py` + `gateway/agent_runner.py` | Add `enabled_tools` guard, align with MCP behavior |

### New Capabilities Architecture

```
Plugin
  ├─► manifest.yaml          ← declares config schema (field name/type/default)
  ├─► plugin.py              ← plugin logic
  └─► [DB] plugin_configs    ← new table: stores user config values (Fernet-encrypted sensitive fields)

Frontend Plugin Management Page
  ├─► Installed plugin list (enable/disable toggle)
  ├─► Click plugin → display config form (generated from manifest.yaml)
  └─► Save → POST /api/plugins/{id}/config
```

### File Changes

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add `PluginConfig` table (plugin_id / user_id / key / value / is_secret) |
| `backend/app/plugins/manifest.py` | **New**: parse `manifest.yaml` schema |
| `backend/app/api/plugins.py` | Extend: add config CRUD, enable/disable endpoints |
| `backend/alembic/versions/` | New migration script |
| `frontend/src/pages/Plugins.vue` | **New**: plugin marketplace management page |
| `frontend/src/api/plugins.ts` | Extend: config-related API calls |

### RBAC Integration

Reuse existing RBAC role system:
- `admin`: install/uninstall plugins, manage global config, control per-plugin user whitelist
- `user`: enable/disable plugins they have permission for (whitelist controlled by admin)

### Worktree

`feature/plugin-enhancement`, branch from `dev` (handle `chat.py` merge conflicts after RAG merges)

---

## Feature C: Multi-Agent Orchestration

### Overall Architecture

```
User Message
    │
    ▼
[Router Agent] — classify task type
    │
    ├─► Simple task → existing ReAct Agent (unchanged)
    │
    └─► Complex task → [Supervisor Agent]
            │
            ├─► Task decomposition (SubTask list)
            │
            ├─► Parallel/serial SubAgent dispatch
            │       ├─► CodeAgent (code gen/exec)
            │       ├─► ResearchAgent (search/RAG retrieval)
            │       └─► WritingAgent (text gen/summarization)
            │
            └─► Aggregate results → return to user
```

### Two Modes

**Supervisor Mode** (task orchestration):
- New `agent/supervisor.py`: LangGraph `StateGraph`, nodes = SubAgent calls
- SubAgents share parent `messages` state, results written back to main state
- Serial/parallel determined by Supervisor based on dependency graph

**Expert Routing Mode** (domain dispatch):
- New `agent/router.py`: lightweight LLM call, outputs routing decision (`code`/`research`/`writing`/`general`)
- Each expert Agent has dedicated persona + toolset:
  - `CodeAgent`: code_exec + shell tools
  - `ResearchAgent`: rag_search + web_search tools
  - `WritingAgent`: summarization + document tools

### File Changes

| File | Change |
|------|--------|
| `backend/app/agent/router.py` | **New**: task type classification routing |
| `backend/app/agent/supervisor.py` | **New**: Supervisor orchestration logic |
| `backend/app/agent/experts/` | **New directory**: code/research/writing expert agents |
| `backend/app/agent/graph.py` | Modify: top-level graph integrates router → supervisor entry |
| `backend/app/api/chat.py` | Modify: streaming output supports multi-agent intermediate step display |

### Key Design Decisions

- **Router cost**: use lightweight LLM (e.g., haiku) for classification only — no main model tokens consumed
- **Streaming passthrough**: SubAgent intermediate steps pushed via SSE in real time; frontend can display "Calling CodeAgent..."
- **Timeout protection**: single SubAgent timeout (default 60s) returns partial result instead of total failure
- **Worktree**: `feature/multi-agent`, branch from latest `dev` after RAG + Plugin merge

---

## Merge Order & Conflict Strategy

```
dev
 ├─► feature/rag-agent-integration   (touches: chat.py, graph.py, rag/)
 ├─► feature/plugin-enhancement      (touches: chat.py, plugins/, frontend/)
 └─► feature/multi-agent             (touches: chat.py, agent/, graph.py)

Merge sequence:
1. feature/rag-agent-integration → dev (first, fewest conflicts)
2. feature/plugin-enhancement → dev   (resolve chat.py conflict with RAG changes)
3. feature/multi-agent → dev          (resolve chat.py + graph.py conflicts with both)
```

## Testing Strategy

- Each worktree runs `uv run pytest tests/ -v` independently before merge
- `chat.py` integration tests added for each feature to verify no regression
- Docker compose full-stack smoke test after each merge
