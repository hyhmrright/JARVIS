[中文](../../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# JARVIS

KI-Assistenzplattform mit RAG-Wissensdatenbank, Multi-LLM-Unterstützung und Streaming-Konversationen.

## Technologie-Stack

| Schicht | Technologie |
|---------|-------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Datenbank | PostgreSQL · Redis · Qdrant (Vektordatenbank) |
| Speicher | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## Projektstruktur

```
JARVIS/
├── backend/          # FastAPI-Backend (Python 3.13 + uv)
├── frontend/         # Vue 3-Frontend (Bun)
├── docker-compose.yml
└── pyproject.toml    # Entwicklungswerkzeug-Konfiguration (Wurzelverzeichnis)
```

## Schnellstart

### Full-Stack-Start (empfohlen)

Generieren Sie die Umgebungsvariablen-Datei und starten Sie:

```bash
bash scripts/init-env.sh   # Sichere .env automatisch generieren (nur beim ersten Mal)
docker compose up -d
```

Service-Adressen: Frontend http://localhost:3000 · Backend http://localhost:8000

### Lokale Entwicklung

**Voraussetzungen:** Docker (für Infrastrukturdienste), Python 3.13+, [uv](https://github.com/astral-sh/uv), [Bun](https://bun.sh)

```bash
# Infrastrukturdienste starten
docker compose up -d postgres redis qdrant minio

# Backend
cd backend
uv sync
uv run alembic upgrade head           # Datenbankmigrationen ausführen
uv run uvicorn app.main:app --reload  # Entwicklungsserver (:8000)

# Frontend (neues Terminal)
cd frontend
bun install
bun run dev                           # Entwicklungsserver (:5173)
```

## Entwicklung

### Codequalität

```bash
# Backend (im Verzeichnis backend/)
uv run ruff check --fix && uv run ruff format
uv run pyright
uv run pytest tests/ -v

# Frontend (im Verzeichnis frontend/)
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # Git Hooks installieren (im Wurzelverzeichnis ausführen)
pre-commit run --all-files
```

## Umgebungsvariablen

Führen Sie `bash scripts/init-env.sh` aus, um automatisch eine sichere `.env` mit zufälligen Passwörtern und Schlüsseln zu generieren.

Das Skript konfiguriert: `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `DATABASE_URL`, `REDIS_URL`.

Nur `DEEPSEEK_API_KEY` muss manuell eingetragen werden. Details finden Sie in `.env.example`.
