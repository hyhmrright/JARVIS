[中文](GEMINI.md) | [English](docs/i18n/gemini-md/GEMINI.en.md) | [日本語](docs/i18n/gemini-md/GEMINI.ja.md) | [한국어](docs/i18n/gemini-md/GEMINI.ko.md) | [Français](docs/i18n/gemini-md/GEMINI.fr.md) | [Deutsch](docs/i18n/gemini-md/GEMINI.de.md)

# Jarvis 项目上下文

本文档为 Gemini 提供关于 `JARVIS` monorepo 的准确上下文信息。

## 项目概览

**名称**: Jarvis AI 助手
**架构**: 多服务 monorepo（FastAPI 后端 + Vue 3 前端）
**目的**: 具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台。

## 目录结构

```
JARVIS/
├── backend/          # FastAPI 后端服务（Python 3.13 + SQLAlchemy + LangGraph）
├── frontend/         # Vue 3 前端（Vite + TypeScript + Pinia）
├── docker-compose.yml
├── pyproject.toml    # 根目录（仅开发工具，无运行时依赖）
└── CLAUDE.md / GEMINI.md
```

## 后端架构（backend/）

- **框架**: FastAPI + Uvicorn
- **数据库**: PostgreSQL（asyncpg 驱动）+ SQLAlchemy async ORM + Alembic 迁移
- **缓存**: Redis
- **向量存储**: Qdrant（RAG 知识库）
- **对象存储**: MinIO（文件上传）
- **LLM**: LangGraph + LangChain，支持 DeepSeek / OpenAI / Anthropic
- **认证**: JWT（python-jose）+ bcrypt（passlib）

### 主要模块

```
backend/app/
├── api/          # FastAPI 路由（auth、conversations、documents、settings）
├── agent/        # LangGraph agent graph + LLM 工厂
├── core/         # 配置（pydantic-settings）、数据库、安全工具
├── models/       # SQLAlchemy ORM 模型
├── rag/          # 文档解析、分块、Qdrant 索引
└── main.py       # 应用入口（CORS、路由注册、健康检查）
```

## 前端架构（frontend/）

- **框架**: Vue 3 + TypeScript + Vite
- **状态管理**: Pinia（auth store、chat store）
- **路由**: Vue Router 4（懒加载 + 路由守卫）
- **UI**: 自定义 CSS 样式

## 环境与依赖

### 后端（使用 uv）
```bash
cd backend
uv sync                          # 安装依赖
uv run uvicorn app.main:app --reload  # 开发服务器
uv run pytest tests/ -v          # 运行测试
uv run alembic upgrade head      # 执行数据库迁移
```

### 前端（使用 bun）
```bash
cd frontend
bun install                      # 安装依赖
bun run dev                      # 开发服务器
bun run build                    # 生产构建
bun run lint                     # ESLint 检查
bun run type-check               # TypeScript 类型检查
```

### Docker 环境
```bash
docker-compose up -d             # 启动所有服务（PostgreSQL、Redis、Qdrant、MinIO、backend、frontend）
```

## 开发工作流

### 分支策略
- **main**: 稳定版本（部署分支）
- **dev**: 日常开发分支（所有改动在此进行）
- 仅在明确指令时将 `dev` 合并至 `main`

### 代码质量工具

**后端**:
- `ruff check --fix && ruff format`：Lint + 格式化
- `pyright`：类型检查
- `pytest`：测试

**前端**:
- `bun run lint`：ESLint 检查
- `bun run type-check`：TypeScript 类型检查

**提交前（pre-commit hooks 自动运行）**:
- YAML/TOML/JSON 格式检查
- uv.lock 同步检查
- ruff lint + format
- 前端 ESLint + TypeScript 类型检查

## 关键配置

- **DATABASE_URL**: `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL**: `redis://localhost:6379`
- **JWT_SECRET**: 通过环境变量配置
- **DEEPSEEK_API_KEY**: 通过环境变量配置
- **Alembic 迁移**: 自动从 `DATABASE_URL` 读取并转换为 psycopg2 同步驱动
