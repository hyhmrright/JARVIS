[中文](README.md) | [English](docs/i18n/readme/README.en.md) | [日本語](docs/i18n/readme/README.ja.md) | [한국어](docs/i18n/readme/README.ko.md) | [Français](docs/i18n/readme/README.fr.md) | [Deutsch](docs/i18n/readme/README.de.md)

# JARVIS

具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台。采用暗黑奢华（Dark Luxury）设计风格，打造高端 AI 交互体验。

## 特性

- **多模型支持** — DeepSeek / OpenAI / Anthropic，可在设置中自由切换
- **RAG 知识库** — 上传文档（PDF/TXT/MD/DOCX），自动分块、向量化存储
- **流式对话** — SSE 实时流式输出，逐字显示 AI 回复
- **LangGraph Agent** — ReAct 循环架构，支持代码执行、文件操作等工具调用
- **暗黑奢华 UI** — 玻璃拟态卡片、金色渐变点缀、精致动画过渡
- **多语言** — 支持中/英/日/韩/法/德 6 种语言
- **全栈 Docker** — 一键 `docker compose up -d` 启动完整服务

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 前端 | Vue 3 · TypeScript · Vite · Pinia |
| 数据库 | PostgreSQL · Redis · Qdrant（向量库）|
| 存储 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
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
├── docker-compose.yml # 全栈编排
└── pyproject.toml     # 根目录开发工具配置
```

## 快速开始

### 全栈启动（推荐）

生成环境变量文件，然后启动：

```bash
bash scripts/init-env.sh   # 自动生成安全的 .env（首次运行）
docker compose up -d
```

服务地址：前端 http://localhost:3000 · 后端 http://localhost:8000

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
uv run pyright
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

脚本会自动配置：`POSTGRES_PASSWORD`、`MINIO_ROOT_USER/PASSWORD`、`REDIS_PASSWORD`、`JWT_SECRET`、`ENCRYPTION_KEY`、`DATABASE_URL`、`REDIS_URL`。

你只需手动填写 `DEEPSEEK_API_KEY`。详见 `.env.example`。
