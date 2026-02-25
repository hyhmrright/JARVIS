[中文](docs/i18n/zh/README.md) | [日本語](docs/i18n/ja/README.md) | [한국어](docs/i18n/ko/README.md) | [Français](docs/i18n/fr/README.md) | [Deutsch](docs/i18n/de/README.md)

# JARVIS

> An AI assistant platform with RAG knowledge base, multi-LLM support, and real-time streaming conversations — featuring a Dark Luxury design language.

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## Features

- **Multi-Model Support** — DeepSeek / OpenAI / Anthropic, switchable per-user in Settings
- **RAG Knowledge Base** — Upload PDF / TXT / MD / DOCX with automatic chunking and vector indexing
- **Streaming Chat** — SSE token-by-token output via LangGraph ReAct agent
- **Dark Luxury UI** — Glassmorphism cards, gold gradient accents, smooth animation transitions
- **Multilingual** — 6 languages: Chinese / English / Japanese / Korean / French / German
- **Production-grade Infrastructure** — 4-layer network isolation, Traefik edge router, Prometheus + Grafana observability

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

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **Local development only** additionally requires [Bun](https://bun.sh) for the frontend.

## Quick Start

### 1. Clone and generate environment

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh   # generates .env with random secure credentials
```

> Requires `uv` (used internally to generate the Fernet encryption key). No other setup needed.

### 2. Add your LLM API key

Open `.env` and fill in at least one key:

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # optional
ANTHROPIC_API_KEY=sk-ant-... # optional
```

### 3. Start

```bash
docker compose up -d
```

First run builds the Docker images — allow a few minutes. Once healthy:

| Service | URL | Available |
|---------|-----|-----------|
| **App** | http://localhost | always |
| Grafana (monitoring) | http://localhost:3001 | always |
| Traefik dashboard | http://localhost:8080/dashboard/ | dev only |
| Backend API (direct) | http://localhost:8000 | dev only |

> The default `docker compose up -d` auto-merges `docker-compose.override.yml`, which exposes debug ports and enables hot-reload for backend code. For production, see below.

### Troubleshooting

**Services fail to start** — check logs:
```bash
docker compose logs backend
docker compose logs traefik
```

**Rebuild from scratch** (after changing Dockerfiles or dependencies):
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**Port conflict on `:80`** — stop whatever holds port 80, then retry.

---

## Docker Compose Files

This project uses two compose files that work together:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | **Base (production)** — minimal surface: only `:80` and `:3001` exposed |
| `docker-compose.override.yml` | **Dev overrides** — auto-merged by Docker Compose; adds debug ports, hot-reload |

Docker Compose automatically merges the override file when you run `docker compose up -d`, so **no extra flags are needed for local development**. For production, explicitly exclude it:

```bash
# Development (default) — merges both files automatically
docker compose up -d

# Production — base file only, no debug ports, no hot-reload
docker compose -f docker-compose.yml up -d
```

## Production Deploy

```bash
docker compose -f docker-compose.yml up -d
```

Exposed ports: `:80` (app) and `:3001` (Grafana) only.

---

## Local Development

Run backend and frontend natively for faster iteration.

**Step 1 — start infrastructure:**

```bash
docker compose up -d postgres redis qdrant minio
```

**Step 2 — backend** (new terminal, from repo root):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**Step 3 — frontend** (new terminal, from repo root):

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173  (proxies /api → localhost:8000)
```

---

## Project Structure

```
JARVIS/
├── backend/                    # FastAPI (Python 3.13 + uv)
│   ├── app/
│   │   ├── agent/              # LangGraph ReAct agent
│   │   ├── api/                # HTTP routes (auth/chat/conversations/documents/settings)
│   │   ├── core/               # Config, JWT/bcrypt/Fernet security, rate limiting
│   │   ├── db/                 # SQLAlchemy async models + sessions
│   │   ├── infra/              # Qdrant / MinIO / Redis singletons
│   │   ├── rag/                # Document chunker + embedder + indexer
│   │   └── tools/              # LangGraph tools (search/code_exec/file/datetime)
│   ├── alembic/                # Database migrations
│   └── tests/                  # pytest suite
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Axios singleton + auth interceptor
│       ├── stores/             # Pinia stores (auth + chat)
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n (zh/en/ja/ko/fr/de)
├── database/                   # Docker init scripts (postgres/redis/qdrant)
├── monitoring/                 # Prometheus config + Grafana provisioning
├── traefik/                    # Traefik dynamic routing config
├── scripts/
│   └── init-env.sh             # Generates secure .env (requires uv)
├── docker-compose.yml          # Base orchestration
├── docker-compose.override.yml # Dev overrides (debug ports + hot-reload)
└── .env.example                # Environment variable reference
```

---

## Development

### Code Quality

```bash
# Backend (run from backend/)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# Frontend (run from frontend/)
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# Run from repo root
pre-commit install
pre-commit run --all-files
```

Hooks: YAML/TOML/JSON validation · uv.lock sync · Ruff lint+format · ESLint · mypy · vue-tsc · gitleaks secret scanning · block direct commits to `main`.

---

## Environment Variables

`bash scripts/init-env.sh` auto-generates all credentials. You only need to supply an LLM API key.

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `MINIO_ROOT_USER/PASSWORD` | MinIO object storage credentials |
| `REDIS_PASSWORD` | Redis auth password |
| `JWT_SECRET` | JWT signing secret |
| `ENCRYPTION_KEY` | Fernet key for encrypting user API keys at rest |
| `GRAFANA_PASSWORD` | Grafana admin password |
| `DEEPSEEK_API_KEY` | **Fill in manually** |
| `OPENAI_API_KEY` | Optional |
| `ANTHROPIC_API_KEY` | Optional |

See `.env.example` for the full reference.

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

[MIT](LICENSE)
