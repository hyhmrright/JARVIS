[English](../../../.github/CONTRIBUTING.md) | [中文](CONTRIBUTING.md)

# 贡献 JARVIS

感谢你对 JARVIS 项目的关注！

## 前置条件

- [Docker](https://docs.docker.com/get-docker/)（用于基础服务）
- [Python 3.13+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) — Python 包管理器
- [Bun](https://bun.sh) — 前端包管理器
- [Git](https://git-scm.com/)

## 快速开始

**1. Fork 并克隆**

```bash
gh repo fork hyhmrright/JARVIS --clone
cd JARVIS
```

**2. 设置环境**

```bash
bash scripts/init-env.sh                              # 生成 .env（仅首次）
docker compose up -d postgres redis qdrant minio      # 启动基础服务
```

**3. 安装依赖**

```bash
cd backend && uv sync && cd ..
cd frontend && bun install && cd ..
pre-commit install
```

**4. 执行数据库迁移**

```bash
cd backend && uv run alembic upgrade head && cd ..
```

**5. 启动开发服务器**

```bash
# 终端 1 — 后端
cd backend && uv run uvicorn app.main:app --reload

# 终端 2 — 前端
cd frontend && bun run dev
```

前端：http://localhost:5173 · 后端：http://localhost:8000

## 分支命名规范

所有分支必须从 `dev`（默认分支）创建：

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能 | `feature/rag-agent-integration` |
| `fix/` | 缺陷修复 | `fix/sse-disconnect` |
| `docs/` | 仅文档 | `docs/api-reference` |
| `infra/` | Docker、CI、配置 | `infra/add-healthcheck` |

## Commit 消息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<类型>: <简短描述>
```

类型：`feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`、`ci`

示例：
- `feat: 将 RAG 检索接入 agent 对话流`
- `fix: 修复 SSE 流超时断连问题`

## Pull Request 流程

1. 从 `dev` 创建分支：`git checkout -b feature/your-feature dev`
2. 进行开发
3. 运行质量检查：`pre-commit run --all-files`
4. 运行测试：`cd backend && uv run pytest tests/ -v`
5. 前端检查：`cd frontend && bun run type-check`
6. 推送并向 **`dev`** 发起 PR（不是 `main`）
7. 填写 PR 模板，等待 CI 通过和维护者审核

## 使用 Git Worktree 并行开发

无需切换分支即可同时开发多个功能：

```bash
# 创建隔离的工作目录
git worktree add .worktrees/my-feature -b feature/my-feature dev

# 初始化工作目录
cd .worktrees/my-feature
cp ../../.env .
cd backend && uv sync && cd ..
cd frontend && bun install && cd ..

# 完成后移除
cd ../..
git worktree remove .worktrees/my-feature
```

**多个开发服务器并行时的端口分配：**

| 工作目录 | 后端 | 前端 |
|---------|------|------|
| 根目录 | 8000 | 5173 |
| Worktree 1 | 8001 | 5174 |
| Worktree 2 | 8002 | 5175 |

## 代码风格

- **Python**：Ruff（lint + 格式化）、Pyright（类型检查）
- **TypeScript/Vue**：ESLint + Prettier、vue-tsc（类型检查）
- 全部通过 pre-commit hooks 强制执行

## 寻找可参与的 Issue

- [`good first issue`](https://github.com/hyhmrright/JARVIS/labels/good%20first%20issue) — 适合新手的 issue
- [`help wanted`](https://github.com/hyhmrright/JARVIS/labels/help%20wanted) — 维护者请求帮助
- [Discussions](https://github.com/hyhmrright/JARVIS/discussions) — 提问和讨论
