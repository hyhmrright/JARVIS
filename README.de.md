[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

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

Kopieren und füllen Sie die Umgebungsvariablen-Datei aus, dann starten Sie:

```bash
cp .env.example .env   # Tragen Sie Ihre Secrets ein
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

Erstellen Sie eine `.env`-Datei im Projektstammverzeichnis:

```env
# Datenbank
POSTGRES_PASSWORD=your_password

# Objektspeicher
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# Authentifizierung
JWT_SECRET=your_jwt_secret

# LLM (Standard-Provider; API-Schlüssel anderer Provider werden pro Benutzer über die Einstellungsseite konfiguriert)
DEEPSEEK_API_KEY=your_key
```

Für die lokale Entwicklung benötigt das Backend zusätzlich `backend/.env` zur Verbindung mit lokalen Diensten:

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Fernet-Verschlüsselungsschlüssel (wird zur Verschlüsselung von Benutzer-API-Schlüsseln verwendet)
# Generierung: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```
