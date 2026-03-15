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

### Backend / 后端 (backend/)
- **Framework**: FastAPI (Python 3.13) + Uvicorn.
- **Graph Engine**: `agent/compiler.py` dynamically compiles Studio JSON DSL into LangGraph `StateGraph`.
- **Skill Registry**: `services/skill_market.py` handles remote skill fetching and dynamic installation.
- **Agent Engine**: `agent/graph.py` supports multimodal inputs and persona-based system prompts.
- **Streaming**: SSE handling in `api/chat.py` integrated with custom workflow execution.
- **RAG Pipeline**: Sliding window chunking (500 words/50 overlap) -> `OpenAIEmbeddings` -> Qdrant.
- **Infrastructure Clients**: Qdrant (lazy async init), MinIO, PostgreSQL (SQLAlchemy asyncpg).

### Frontend / 前端 (frontend/)
- **Framework / 框架**: Vue 3 + TypeScript + Vite.
- **Workflow Studio**: Based on `VueFlow`, allows visual orchestration of nodes.
- **Market & Personas**: Dedicated pages for ecosystem expansion.
- **Dashboards**: `UsagePage.vue` enhanced with `vue-echarts` for real-time monitoring.
- **State / 状态管理**: Pinia stores (`auth.ts`, `chat.ts`, `workspace.ts`).
- **Streaming / 流式处理**: SSE handled via native `fetch` + `ReadableStream`.
- **API Client**: Axios with `/api` base, JWT interceptors, and 401 auto-logout.

## Gemini Enhanced Capabilities / Gemini 增强功能

Gemini CLI offers specialized tools and skills that should be utilized for JARVIS development:
Gemini CLI 提供了专用的工具和技能，应在开发中充分利用：

### 1. Specialized Skills / 专用技能 (`activate_skill`)
- **`using-superpowers`**: Always active. Guides on using other skills / 引导如何使用其他技能。
- **`using-git-worktrees`**: Mandatory for parallel development / 用于并行开发的强制性工具。
- **`test-driven-development`**: Use when implementing new features or bug fixes / 实现新功能或修复 Bug 时使用。
- **`systematic-debugging`**: Use for complex issues or test failures / 用于处理复杂问题或测试失败。
- **`brainstorming`**: Use before starting any new feature design / 开始任何新功能设计前使用。
- **`chrome-devtools`**: Use for frontend UI debugging / 用于前端 UI 调试和交互自动化。

### 2. Sub-Agents / 子代理
- **`codebase_investigator`**: Use for architectural mapping and deep impact analysis / 用于架构映射和深度影响分析。
- **`generalist`**: Use for batch refactoring or high-volume updates / 用于批量重构或大规模文件更新。

## Development Workflow / 开发工作流

### Branch Strategy / 分支策略
- **main**: Release branch. No direct commits / 发布分支，禁止直接提交。
- **dev**: Primary integration branch (default) / 主要集成分支（默认）。
- **feature/fix/docs/infra/...**: Create from `dev`, named `<type>/<short-description>`.
- **Flow**: feature branch → merge to `dev` → merge to `main` (only on explicit request).

### Worktree Parallel Development / Worktree 并行开发
Use the `using-git-worktrees` skill to manage multiple features.
- **Port Mapping / 端口映射**:
  - Main (root): Backend 8000 / Frontend 3000
  - Worktree 1: Backend 8001 / Frontend 3100
  - Worktree 2: Backend 8002 / Frontend 3200

### Mandatory Quality Loop (Self-Check) / 强制质量循环 (自检流程)
Before every `git commit` or `git push`, you **must** execute the quality loop:
在每次 `git commit` 或 `git push` 之前，**必须**执行质量循环：

1. **Static Analysis / 静态分析**:
   - `cd backend && uv run ruff check --fix && uv run ruff format`
   - `cd backend && uv run mypy app`
   - `cd frontend && bun run lint && bun run type-check`
2. **Review & Refinement / 审查与精炼**:
   - Use `activate_skill("requesting-code-review")` or `activate_skill("code-review-commons")`.
   - Use `activate_skill("verification-before-completion")` before claiming work is finished.
3. **Commit & Push / 提交与推送**:
   - Always propose a clear commit message (Conventional Commits: `feat: ...`, `fix: ...`).
   - Use `git commit --amend` pre-push to keep history clean if fixes were applied during review.

## Common Commands / 常用命令

### Setup & Run / 设置与运行
```bash
bash scripts/init-env.sh         # Initialize environment / 初始化环境 (生成 .env)
uv sync                          # Install backend deps / 安装后端依赖
cd frontend && bun install       # Install frontend deps / 安装前端依赖

# Start infra only / 仅启动基础设施
docker compose up -d postgres redis qdrant minio

# Run Dev Servers / 启动开发服务器
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && bun run dev --port 3000
```

### Testing / 测试
```bash
# Run in backend/ directory / 在 backend/ 目录执行
uv run pytest tests/ -v          # All tests / 所有测试
uv run pytest --collect-only -q  # Fast import check / 快速 import 检查
```
*Note: Each test runs in its own event loop. Beware of module-level `AsyncSessionLocal` contamination.*

## Global Memories / 全局记忆 (Gemini Preferences)
- **Comments / 注释**: Always use Chinese (中文) for code comments and documentation.
- **State Models / 状态模型**: Prefer `dataclasses.dataclass` for AgentState to avoid TypedDict issues.
- **Language / 语言**: Always respond to the user in Simplified Chinese (简体中文).

---
*For manual navigation or deep research, invoke `codebase_investigator` with your objective.*
