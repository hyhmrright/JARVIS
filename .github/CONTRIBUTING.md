[English](CONTRIBUTING.md) | [中文](../docs/i18n/zh/CONTRIBUTING.md)

# Contributing to JARVIS

Thank you for your interest in contributing to JARVIS!

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (for infrastructure services)
- [Python 3.13+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) — Python package manager
- [Bun](https://bun.sh) — frontend package manager
- [Git](https://git-scm.com/)

## Getting Started

**1. Fork and clone**

```bash
gh repo fork hyhmrright/JARVIS --clone
cd JARVIS
```

**2. Set up environment**

```bash
bash scripts/init-env.sh                              # generate .env (first time only)
docker compose up -d postgres redis qdrant minio      # start infrastructure
```

**3. Install dependencies**

```bash
cd backend && uv sync && cd ..
cd frontend && bun install && cd ..
pre-commit install
```

**4. Run database migrations**

```bash
cd backend && uv run alembic upgrade head && cd ..
```

**5. Start development servers**

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && bun run dev
```

Frontend: http://localhost:3000 · Backend: http://localhost:8000

## Branch Naming

All branches must be created from `dev` (the default branch):

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New feature | `feature/rag-agent-integration` |
| `fix/` | Bug fix | `fix/sse-disconnect` |
| `docs/` | Documentation only | `docs/api-reference` |
| `infra/` | Docker, CI, config | `infra/add-healthcheck` |

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

Examples:
- `feat: add RAG retrieval to agent conversation`
- `fix: resolve SSE stream disconnect on timeout`

## Pull Request Process

1. Create a branch from `dev`: `git checkout -b feature/your-feature dev`
2. Make your changes
3. Run quality checks: `pre-commit run --all-files`
4. Run tests: `cd backend && uv run pytest tests/ -v`
5. Run frontend checks: `cd frontend && bun run type-check`
6. Push and open a PR targeting **`dev`** (not `main`)
7. Fill in the PR template
8. Wait for CI to pass and a maintainer review

## Using Git Worktrees

Work on multiple features simultaneously without switching branches:

```bash
# Create an isolated workspace
git worktree add .worktrees/my-feature -b feature/my-feature dev

# Set up the worktree
cd .worktrees/my-feature
cp ../../.env .
cd backend && uv sync && cd ..
cd frontend && bun install && cd ..

# When done
cd ../..
git worktree remove .worktrees/my-feature
```

**Port allocation for parallel dev servers:**

| Workspace | Backend | Frontend |
|-----------|---------|----------|
| Root | 8000 | 3000 |
| Worktree 1 | 8001 | 3100 |
| Worktree 2 | 8002 | 3200 |

```bash
# In a worktree, use different ports
cd backend && uv run uvicorn app.main:app --reload --port 8001
cd frontend && bun run dev --port 3100
```

## Code Style

- **Python**: Ruff (lint + format), mypy (type check)
- **TypeScript/Vue**: ESLint + Prettier, vue-tsc (type check)
- All enforced via pre-commit hooks

## Finding Issues

- [`good first issue`](https://github.com/hyhmrright/JARVIS/labels/good%20first%20issue) — newcomer-friendly
- [`help wanted`](https://github.com/hyhmrright/JARVIS/labels/help%20wanted) — maintainer requests help
- [Discussions](https://github.com/hyhmrright/JARVIS/discussions) — ask questions
