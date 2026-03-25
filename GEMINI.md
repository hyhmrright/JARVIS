# Jarvis Project Context / 项目上下文 (Gemini Edition)

This document provides Gemini with comprehensive context and operational guidelines for the `JARVIS` monorepo.
本文档为 Gemini 提供关于 `JARVIS` monorepo 的全面上下文和操作指南。

## Project Overview / 项目概览

**Name / 名称**: Jarvis AI Assistant
**Architecture / 架构**: Multi-service monorepo (FastAPI backend + Vue 3 frontend)
**Purpose / 目的**: AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations.

**Completed Features (Phase 1-12 + AI OS Epic)**:
- **Vision & Multimodal**: Support for image upload and analysis in chat.
- **Branching & Editing**: Tree-based conversation flow with historical message editing.
- **Public Sharing**: Generate read-only public links for sharing conversations.
- **Skill Market**: Dynamic skill discovery and 1-click installation from remote registries.
- **Personas**: Custom system prompt management and selection.
- **Workflow Engine**: Node-based visual studio for orchestrating complex AI logic (DSL -> LangGraph).
- **LLMOps Dashboard**: Visual consumption and performance metrics via ECharts.
- **RAG Knowledge Base**: Qdrant indexing, sliding window chunking, cross-collection search.
- **Agent Intelligence**: LangGraph ReAct agents with tools: `search`, `code_exec`, `datetime`, `file`, `shell`, `browser`, `rag`.
- **Infrastructure**: Gateway (Traefik), Cron trigger system, Webhooks, Canvas rendering.
- **Voice**: Integrated TTS/STT services.
- **Observability**: Grafana/Loki/Prometheus monitoring stack.
- **Advanced Ecosystem**: Plugin SDK, multi-agent supervisor, audit logs.
- **Multitenancy**: Organizations, Workspaces, Invitations, PATs.

## Core Architecture / 核心架构

### Directory Structure / 目录结构
```
JARVIS/
├── backend/           # FastAPI backend (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # FastAPI entry point
│   │   ├── agent/     # LangGraph ReAct agent (graph/llm/state/persona)
│   │   ├── api/       # HTTP routes
│   │   ├── db/        # SQLAlchemy async models and sessions
│   │   ├── infra/     # Infrastructure client singletons (Qdrant/MinIO/Redis)
│   │   ├── rag/       # RAG pipeline
│   │   └── worker.py  # ARQ worker
│   └── tests/         # pytest test suite
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── stores/    # Pinia stores (auth / chat / workspace)
│       └── pages/     # Feature pages
├── database/          # Docker init scripts
└── docker-compose.yml # Full-stack orchestration
```

### Backend Highlights / 后端架构要点
- **LLM Agent**: `agent/graph.py` 使用 LangGraph `StateGraph` 实现 ReAct 循环。每次请求创建新实例，不持久化 checkpoint。
- **Streaming**: `api/chat.py` 返回 SSE `StreamingResponse`。内部使用独立的 `AsyncSessionLocal`。
- **RAG**: 滑窗分词 (500/50 overlap) -> `OpenAIEmbeddings` -> Qdrant。每用户/工作区独立 collection。
- **Models**: 全部使用 UUID 主键，敏感字段（API Key）使用 Fernet 加密。

## Gemini Enhanced Capabilities / Gemini 增强功能

Gemini CLI 提供了专用的工具和技能，应在开发中充分利用：

### 1. Specialized Skills / 专用技能 (`activate_skill`)
- **`using-superpowers`**: Always active. 引导如何使用其他技能。
- **`brainstorming`**: 开始任何新功能设计前必须使用。
- **`test-driven-development`**: 实现新功能或修复 Bug 时使用。
- **`systematic-debugging`**: 用于处理复杂问题或测试失败。
- **`chrome-devtools`**: 用于前端 UI 调试和交互自动化。
- **`using-git-worktrees`**: 必须用于并行开发。

### 2. Sub-Agents / 子代理
- **`codebase_investigator`**: 用于架构映射和深度影响分析。
- **`generalist`**: 用于批量重构或大规模文件更新。

## Development Workflow / 开发工作流

### Branch Strategy / 分支策略
- **main**: 发布分支，禁止直接提交。
- **dev**: 主要集成分支（默认）。
- **feature/fix/docs/infra/...**: 从 `dev` 创建，命名格式 `<type>/<short-description>`。
- **Flow**: feature branch → merge to `dev` → merge to `main` (仅在明确要求时)。

### Worktree Parallel Development / Worktree 并行开发
使用 `using-git-worktrees` 技能管理多个功能。
- **端口映射**:
  - Main (root): Backend 8000 / Frontend 3000
  - Worktree 1: Backend 8001 / Frontend 3100
  - Worktree 2: Backend 8002 / Frontend 3200

### Mandatory Quality Loop (Self-Check) / 强制质量循环 (自检流程)
在每次 `git commit` 或 `git push` 之前，**必须**执行质量循环：

1. **Static Analysis / 静态分析**:
   - `cd backend && uv run ruff check --fix && uv run ruff format`
   - `cd backend && uv run mypy app`
   - `cd frontend && bun run lint && bun run type-check`
2. **Testing / 测试**:
   - `cd backend && uv run pytest tests/ -x -q --tb=short`
   - 若数据库不可用，至少执行 `uv run pytest --collect-only -q`。
3. **Review & Refinement / 审查与精炼**:
   - 使用 `activate_skill("requesting-code-review")` 进行自我审查。
   - 确保所有修改后的代码注释均使用 **中文**。

## Common Commands / 常用命令

### Setup & Run / 设置与运行
```bash
bash scripts/init-env.sh         # 初始化环境 (生成 .env)
uv sync                          # 安装后端依赖
cd frontend && bun install       # 安装前端依赖
docker compose up -d postgres redis qdrant minio # 启动基础设施
```

## Global Memories / 全局记忆 (Gemini Preferences)
- **Comments / 注释**: 所有的代码注释和文档必须使用 **中文 (Chinese)**。
- **State Models / 状态模型**: 必须优先使用 `dataclasses.dataclass` 定义 AgentState，以避免 Python 3.13 下的 TypedDict 问题。
- **Language / 语言**: 始终使用 **简体中文** 回复用户。

---
*For manual navigation or deep research, invoke `codebase_investigator` with your objective.*
