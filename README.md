[中文](README.md) | [English](docs/i18n/readme/README.en.md) | [日本語](docs/i18n/readme/README.ja.md) | [한국어](docs/i18n/readme/README.ko.md) | [Français](docs/i18n/readme/README.fr.md) | [Deutsch](docs/i18n/readme/README.de.md)

# JARVIS

具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI · LangGraph · SQLAlchemy · Alembic |
| 前端 | Vue 3 · TypeScript · Vite · Pinia |
| 数据库 | PostgreSQL · Redis · Qdrant（向量库）|
| 存储 | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## 项目结构

```
JARVIS/
├── backend/          # FastAPI 后端（Python 3.13 + uv）
├── frontend/         # Vue 3 前端（Bun）
├── docker-compose.yml
└── pyproject.toml    # 根目录开发工具配置
```

## 快速开始

### 全栈启动（推荐）

复制并填写环境变量文件，然后启动：

```bash
cp .env.example .env   # 填写各项密钥
docker compose up -d
```

服务地址：前端 http://localhost:3000 · 后端 http://localhost:8000

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

在项目根目录创建 `.env` 文件：

```env
# 数据库
POSTGRES_PASSWORD=your_password

# 对象存储
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# 认证
JWT_SECRET=your_jwt_secret

# LLM（默认 provider，其他 provider 的 API Key 通过应用设置页面按用户配置）
DEEPSEEK_API_KEY=your_key
```

本地开发时后端还需配置 `backend/.env`，连接本地服务：

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Fernet 加密密钥（用于加密用户 API Key）
# 生成方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```
