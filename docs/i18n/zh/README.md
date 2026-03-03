[English](../../../README.md) | [中文](README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md)

# JARVIS

> 具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台——采用暗黑奢华（Dark Luxury）设计风格。

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## 特性

- **多模型支持** — DeepSeek / OpenAI / Anthropic，可在设置中按用户自由切换
- **RAG 知识库** — 上传 PDF / TXT / MD / DOCX，自动分块、向量化索引
- **流式对话** — 通过 LangGraph ReAct agent 实现 SSE 逐 token 输出
- **暗黑奢华 UI** — 玻璃拟态卡片、金色渐变点缀、流畅动画过渡
- **多语言** — 支持 6 种语言：中文 / English / 日本語 / 한국어 / Français / Deutsch
- **生产级基础设施** — 4 层网络隔离、Traefik 边缘路由、Prometheus + Grafana 可观测性

## 系统限制（沙箱隔离）

为了保证系统的安全性，JARVIS 严格运行在一个隔离的 Docker 容器环境中。

- **无宿主机访问权限**：JARVIS 无法直接在您的本地物理宿主机系统（如 macOS、Windows、Linux）上执行命令。
- **无法原生安装软件**：它无法为您在本地物理电脑上安装原生软件（例如运行 `brew install`、`apt-get` 或 `npm install -g`）。
- **隔离执行**：AI 执行的任何终端命令（如 Python 脚本或 shell 工具）都严格限制在后端 Docker 容器或专属沙箱容器内部，与您的主操作系统完全隔离。

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

## 前置条件

| 工具 | 版本 | 安装方式 |
|------|------|---------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | 最新版 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **仅本地开发**额外需要 [Bun](https://bun.sh) 用于前端。

## 快速开始

### 1. 克隆并生成环境变量

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh
```

> 需要安装 `uv`（内部用于生成 Fernet 加密密钥）。无需其他额外设置。

### 2. 填写 LLM API 密钥

打开 `.env`，填写至少一个密钥：

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # 可选
ANTHROPIC_API_KEY=sk-ant-... # 可选
```

### 3. 启动

```bash
docker compose up -d
```

首次运行会构建 Docker 镜像——请等待几分钟。启动完成后：

| 服务 | 地址 | 可用模式 |
|------|-----|---------|
| **应用** | http://localhost | 始终可用 |
| Grafana（监控） | http://localhost:3001 | 始终可用 |
| Traefik 面板 | http://localhost:8080/dashboard/ | 仅开发 |
| 后端 API（直连） | http://localhost:8000 | 仅开发 |

> 默认的 `docker compose up -d` 会自动合并 `docker-compose.override.yml`，暴露调试端口并启用后端代码热重载。生产环境请参见下文。

### 故障排查

**服务启动失败** — 查看日志：
```bash
docker compose logs backend
docker compose logs traefik
```

**从头重新构建**（修改 Dockerfile 或依赖后）：
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**`:80` 端口冲突** — 停止占用 80 端口的进程后重试。

---

## Docker Compose 文件

本项目使用两个协同工作的 compose 文件：

| 文件 | 用途 |
|------|------|
| `docker-compose.yml` | **基础（生产）** — 最小暴露面：仅开放 `:80` 和 `:3001` |
| `docker-compose.override.yml` | **开发覆盖** — 由 Docker Compose 自动合并；添加调试端口、热重载 |

运行 `docker compose up -d` 时，Docker Compose 会自动合并覆盖文件，因此**本地开发无需任何额外参数**。生产环境需显式排除：

```bash
# 开发（默认）— 自动合并两个文件
docker compose up -d

# 生产 — 仅使用基础文件，无调试端口，无热重载
docker compose -f docker-compose.yml up -d
```

## 生产部署

```bash
docker compose -f docker-compose.yml up -d
```

仅暴露 `:80`（应用）和 `:3001`（Grafana）端口。

---

## 本地开发

在本地运行后端和前端，迭代更快。

**第一步 — 启动基础服务：**

```bash
docker compose up -d postgres redis qdrant minio
```

**第二步 — 后端**（新终端，在仓库根目录）：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**第三步 — 前端**（新终端，在仓库根目录）：

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173（代理 /api → localhost:8000）
```

---

## 项目结构

```
JARVIS/
├── backend/                    # FastAPI（Python 3.13 + uv）
│   ├── app/
│   │   ├── agent/              # LangGraph ReAct agent
│   │   ├── api/                # HTTP 路由（auth/chat/conversations/documents/settings）
│   │   ├── core/               # 配置、JWT/bcrypt/Fernet 安全、限流
│   │   ├── db/                 # SQLAlchemy 异步模型 + 会话
│   │   ├── infra/              # Qdrant / MinIO / Redis 单例
│   │   ├── rag/                # 文档分块 + 向量化 + 索引
│   │   └── tools/              # LangGraph 工具（search/code_exec/file/datetime）
│   ├── alembic/                # 数据库迁移
│   └── tests/                  # pytest 测试套件
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Axios 单例 + 认证拦截器
│       ├── stores/             # Pinia stores（auth + chat）
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n（zh/en/ja/ko/fr/de）
├── database/                   # Docker 初始化脚本（postgres/redis/qdrant）
├── monitoring/                 # Prometheus 配置 + Grafana 预置
├── traefik/                    # Traefik 动态路由配置
├── scripts/
│   └── init-env.sh             # 生成安全 .env（需要 uv）
├── docker-compose.yml          # 基础编排
├── docker-compose.override.yml # 开发覆盖（调试端口 + 热重载）
└── .env.example                # 环境变量参考
```

---

## 开发

### 代码质量

```bash
# 后端（在 backend/ 目录执行）
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# 前端（在 frontend/ 目录执行）
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# 在仓库根目录执行
pre-commit install
pre-commit run --all-files
```

Hooks 包含：YAML/TOML/JSON 校验 · uv.lock 同步 · Ruff lint+format · ESLint · mypy · vue-tsc · gitleaks 密钥扫描 · 禁止直接提交 `main`。

---

## 环境变量

`bash scripts/init-env.sh` 会自动生成所有凭证。你只需提供 LLM API 密钥。

| 变量 | 说明 |
|------|------|
| `POSTGRES_PASSWORD` | PostgreSQL 密码 |
| `MINIO_ROOT_USER/PASSWORD` | MinIO 对象存储凭证 |
| `REDIS_PASSWORD` | Redis 认证密码 |
| `JWT_SECRET` | JWT 签名密钥 |
| `ENCRYPTION_KEY` | 用于静态加密用户 API 密钥的 Fernet 密钥 |
| `GRAFANA_PASSWORD` | Grafana 管理员密码 |
| `DEEPSEEK_API_KEY` | **需手动填写** |
| `OPENAI_API_KEY` | 可选 |
| `ANTHROPIC_API_KEY` | 可选 |

完整参考见 `.env.example`。

---

## 贡献

参见 [CONTRIBUTING.md](../../../.github/CONTRIBUTING.md)。

## 许可证

[MIT](../../../LICENSE)
