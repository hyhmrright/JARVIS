[English](../../../README.md) | [中文](README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台。采用暗黑奢华（Dark Luxury）设计风格，打造高端 AI 交互体验。

## 特性

- **多模型支持** — DeepSeek / OpenAI / Anthropic，可在设置中自由切换
- **RAG 知识库** — 上传文档（PDF/TXT/MD/DOCX），自动分块、向量化存储
- **流式对话** — SSE 实时流式输出，逐字显示 AI 回复
- **LangGraph Agent** — ReAct 循环架构，支持代码执行、文件操作等工具调用
- **暗黑奢华 UI** — 玻璃拟态卡片、金色渐变点缀、精致动画过渡
- **多语言** — 支持中/英/日/韩/法/德 6 种语言
- **生产级 Docker** — 4 层网络隔离、Traefik 边缘路由、完整可观测性栈

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 前端 | Vue 3 · TypeScript · Vite · Pinia |
| 数据库 | PostgreSQL · Redis · Qdrant（向量库）|
| 存储 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| 边缘路由 | Traefik v3 |
| 可观测性 | Prometheus · Grafana · cAdvisor |
| 设计 | CSS Variables 设计系统 · 玻璃拟态 · 暗黑主题 |

## 项目结构

```
JARVIS/
├── backend/           # FastAPI 后端（Python 3.13 + uv）
│   ├── app/           # 应用代码（agent/api/core/db/infra/rag/tools）
│   ├── alembic/       # 数据库迁移
│   └── tests/         # pytest 测试套件
├── frontend/          # Vue 3 前端（Bun）
│   └── src/
│       ├── assets/styles/  # CSS 设计系统（global/animations/components）
│       ├── pages/          # 页面组件（Login/Register/Chat/Documents/Settings）
│       ├── stores/         # Pinia 状态管理
│       └── locales/        # i18n 多语言
├── database/          # Docker 初始化脚本（postgres/redis/qdrant）
├── monitoring/        # Prometheus 配置 + Grafana 预置
├── traefik/           # Traefik 动态路由配置
├── docker-compose.yml          # 生产编排（4 层网络）
├── docker-compose.override.yml # 开发覆盖（暴露端口、热重载）
└── pyproject.toml     # 根目录开发工具配置
```

## 快速开始

### 全栈启动（推荐）

生成环境变量文件，然后启动：

```bash
bash scripts/init-env.sh   # 自动生成安全的 .env（首次运行）
docker compose up -d
```

| 服务 | 地址 |
|------|------|
| **应用（经 Traefik）** | http://localhost |
| Grafana（监控） | http://localhost:3001 |
| Traefik 面板 | http://localhost:8080/dashboard/ |
| 后端（直连） | http://localhost:8000 |

> 默认的 `docker compose up -d` 会自动合并 `docker-compose.override.yml`，暴露调试端口并启用热重载。仅供本地开发使用。

### 生产部署（无调试端口）

```bash
docker compose -f docker-compose.yml up -d
```

仅使用基础配置文件——无调试端口、无热重载、无 Traefik 面板。仅暴露 `:80`（应用）和 `:3001`（Grafana）。

> 无缓存重新构建：`docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

### 本地开发

**前置条件：** Docker（用于基础服务）、Python 3.13+、[uv](https://github.com/astral-sh/uv)、[Bun](https://bun.sh)

```bash
# 启动基础服务
docker compose up -d postgres redis qdrant minio

# 后端
cd backend
uv sync
uv run alembic upgrade head           # 执行数据库迁移
uv run uvicorn app.main:app --reload  # 开发服务器（:8000）

# 前端（新终端）
cd frontend
bun install
bun run dev                           # 开发服务器（:5173）
```

## 开发

### 代码质量

```bash
# 后端（在 backend/ 目录）
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# 前端（在 frontend/ 目录）
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # 安装 git hooks（根目录执行）
pre-commit run --all-files
```

## 环境变量

运行 `bash scripts/init-env.sh` 自动生成安全的 `.env`（包含随机密码和密钥）。

脚本会自动配置：`POSTGRES_PASSWORD`、`MINIO_ROOT_USER/PASSWORD`、`REDIS_PASSWORD`、`JWT_SECRET`、`ENCRYPTION_KEY`、`GRAFANA_PASSWORD`、`DATABASE_URL`、`REDIS_URL`。

你只需手动填写 `DEEPSEEK_API_KEY`。详见 `.env.example`。
