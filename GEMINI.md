[中文](docs/i18n/zh/GEMINI.md) | [日本語](docs/i18n/ja/GEMINI.md) | [한국어](docs/i18n/ko/GEMINI.md) | [Français](docs/i18n/fr/GEMINI.md) | [Deutsch](docs/i18n/de/GEMINI.md)

# Jarvis Project Context

This document provides Gemini with accurate context information about the `JARVIS` monorepo.

## Project Overview

**Name**: Jarvis AI Assistant
**Architecture**: Multi-service monorepo (FastAPI backend + Vue 3 frontend)
**Purpose**: AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations.

## Directory Structure

```
JARVIS/
├── backend/          # FastAPI backend service (Python 3.13 + SQLAlchemy + LangGraph)
├── frontend/         # Vue 3 frontend (Vite + TypeScript + Pinia)
├── docker-compose.yml
├── pyproject.toml    # Root directory (dev tools only, no runtime dependencies)
└── CLAUDE.md / GEMINI.md
```

## Backend Architecture (backend/)

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (asyncpg driver) + SQLAlchemy async ORM + Alembic migrations
- **Cache**: Redis
- **Vector Store**: Qdrant (RAG knowledge base)
- **Object Storage**: MinIO (file uploads)
- **LLM**: LangGraph + LangChain, supporting DeepSeek / OpenAI / Anthropic
- **Authentication**: JWT (python-jose) + bcrypt (passlib)

### Main Modules

```
backend/app/
├── api/          # FastAPI routes (auth, conversations, documents, settings)
├── agent/        # LangGraph agent graph + LLM factory
├── core/         # Configuration (pydantic-settings), database, security utilities
├── models/       # SQLAlchemy ORM models
├── rag/          # Document parsing, chunking, Qdrant indexing
└── main.py       # Application entry point (CORS, route registration, health check)
```

## Frontend Architecture (frontend/)

- **Framework**: Vue 3 + TypeScript + Vite
- **State Management**: Pinia (auth store, chat store)
- **Routing**: Vue Router 4 (lazy loading + route guards)
- **UI**: Custom CSS styles

## Environment & Dependencies

### Backend (using uv)
```bash
cd backend
uv sync                          # Install dependencies
uv run uvicorn app.main:app --reload  # Development server
uv run pytest tests/ -v          # Run tests
uv run alembic upgrade head      # Run database migrations
```

### Frontend (using bun)
```bash
cd frontend
bun install                      # Install dependencies
bun run dev                      # Development server
bun run build                    # Production build
bun run lint                     # ESLint check
bun run type-check               # TypeScript type check
```

### Docker Environment
```bash
docker-compose up -d             # Start all services (PostgreSQL, Redis, Qdrant, MinIO, backend, frontend)
```

## Development Workflow

### Branch Strategy
- **main**: Stable version (deployment branch)
- **dev**: Daily development branch (all changes are made here)
- Only merge `dev` into `main` when explicitly instructed

### Code Quality Tools

**Backend**:
- `ruff check --fix && ruff format`: Lint + formatting
- `mypy`: Type checking
- `pytest`: Testing

**Frontend**:
- `bun run lint`: ESLint check
- `bun run type-check`: TypeScript type check

**Pre-commit (pre-commit hooks run automatically)**:
- YAML/TOML/JSON format check
- uv.lock sync check
- ruff lint + format
- Frontend ESLint + TypeScript type check

## Key Configuration

- **DATABASE_URL**: `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL**: `redis://localhost:6379`
- **JWT_SECRET**: Configured via environment variable
- **DEEPSEEK_API_KEY**: Configured via environment variable
- **Alembic migrations**: Automatically reads from `DATABASE_URL` and converts to psycopg2 synchronous driver
