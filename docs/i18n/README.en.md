[中文](../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

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

Copy and fill in the environment variables file, then start:

```bash
cp .env.example .env   # Fill in your secrets
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

Create a `.env` file in the project root:

```env
# Database
POSTGRES_PASSWORD=your_password

# Object Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# Authentication
JWT_SECRET=your_jwt_secret

# LLM (default provider; other providers' API Keys are configured per user via the app settings page)
DEEPSEEK_API_KEY=your_key
```

For local development, the backend also requires `backend/.env` to connect to local services:

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Fernet encryption key (used to encrypt user API Keys)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```
