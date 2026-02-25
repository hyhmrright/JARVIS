[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)

# JARVIS

An AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations. Featuring a Dark Luxury design language for a premium AI interaction experience.

## Features

- **Multi-Model Support** — DeepSeek / OpenAI / Anthropic, freely switchable in settings
- **RAG Knowledge Base** — Upload documents (PDF/TXT/MD/DOCX) with automatic chunking and vector storage
- **Streaming Chat** — SSE real-time streaming output, displaying AI replies token by token
- **LangGraph Agent** — ReAct loop architecture with tool calling for code execution, file operations, and more
- **Dark Luxury UI** — Glassmorphism cards, gold gradient accents, refined animation transitions
- **Multilingual** — Supports 6 languages: Chinese / English / Japanese / Korean / French / German
- **Production-grade Docker** — 4-layer network isolation, Traefik edge router, full observability stack

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Database | PostgreSQL · Redis · Qdrant (Vector DB) |
| Storage | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| Edge Router | Traefik v3 |
| Observability | Prometheus · Grafana · cAdvisor |
| Design | CSS Variables Design System · Glassmorphism · Dark Theme |

## Project Structure

```
JARVIS/
├── backend/           # FastAPI backend (Python 3.13 + uv)
│   ├── app/           # Application code (agent/api/core/db/infra/rag/tools)
│   ├── alembic/       # Database migrations
│   └── tests/         # pytest test suite
├── frontend/          # Vue 3 frontend (Bun)
│   └── src/
│       ├── assets/styles/  # CSS design system (global/animations/components)
│       ├── pages/          # Page components (Login/Register/Chat/Documents/Settings)
│       ├── stores/         # Pinia state management
│       └── locales/        # i18n multilingual
├── database/          # Docker init scripts (postgres/redis/qdrant)
├── monitoring/        # Prometheus config + Grafana provisioning
├── traefik/           # Traefik dynamic routing config
├── docker-compose.yml          # Production orchestration (4-layer networks)
├── docker-compose.override.yml # Dev overrides (exposed ports, hot-reload)
└── pyproject.toml     # Root-level dev tooling config
```

## Quick Start

### Full-Stack Launch (Recommended)

Generate the environment variables file, then start:

```bash
bash scripts/init-env.sh   # Auto-generate a secure .env (first time only)
docker compose up -d
```

| Service | URL | Mode |
|---------|-----|------|
| **App (via Traefik)** | http://localhost | dev + prod |
| Grafana (monitoring) | http://localhost:3001 | dev + prod |
| Traefik dashboard | http://localhost:8080/dashboard/ | dev only |
| Backend (direct) | http://localhost:8000 | dev only |

> The default `docker compose up -d` merges `docker-compose.override.yml` automatically, exposing debug ports (`:8000`, `:8080`, etc.) and enabling hot-reload. This is intended for local development only.

### Production Deploy (no debug ports)

```bash
docker compose -f docker-compose.yml up -d
```

This uses only the base compose file — no debug ports, no hot-reload, no Traefik dashboard. Only `:80` (app) and `:3001` (Grafana) are exposed.

> Rebuild without cache: `docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

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
uv run mypy app
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

The script configures: `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `GRAFANA_PASSWORD`, `DATABASE_URL`, `REDIS_URL`.

You only need to manually fill in `DEEPSEEK_API_KEY`. See `.env.example` for details.
