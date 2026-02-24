[中文](../../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# JARVIS

An AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Database | PostgreSQL · Redis · Qdrant (Vector DB) |
| Storage | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## Project Structure

```
JARVIS/
├── backend/          # FastAPI backend (Python 3.13 + uv)
├── frontend/         # Vue 3 frontend (Bun)
├── docker-compose.yml
└── pyproject.toml    # Root-level dev tooling config
```

## Quick Start

### Full-Stack Launch (Recommended)

Generate the environment variables file, then start:

```bash
bash scripts/init-env.sh   # Auto-generate a secure .env (first time only)
docker compose up -d
```

Service URLs: Frontend http://localhost:3000 · Backend http://localhost:8000

### Local Development

**Prerequisites:** Docker (for infrastructure services), Python 3.13+, [uv](https://github.com/astral-sh/uv), [Bun](https://bun.sh)

```bash
# Start infrastructure services
docker compose up -d postgres redis qdrant minio

# Backend
cd backend
uv sync
uv run alembic upgrade head           # Run database migrations
uv run uvicorn app.main:app --reload  # Dev server (:8000)

# Frontend (new terminal)
cd frontend
bun install
bun run dev                           # Dev server (:5173)
```

## Development

### Code Quality

```bash
# Backend (in backend/ directory)
uv run ruff check --fix && uv run ruff format
uv run pyright
uv run pytest tests/ -v

# Frontend (in frontend/ directory)
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # Install git hooks (run from root)
pre-commit run --all-files
```

## Environment Variables

Run `bash scripts/init-env.sh` to auto-generate a secure `.env` with random passwords and keys.

The script configures: `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `DATABASE_URL`, `REDIS_URL`.

You only need to manually fill in `DEEPSEEK_API_KEY`. See `.env.example` for details.
