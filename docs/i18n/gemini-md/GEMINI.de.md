[中文](../../../GEMINI.md) | [English](GEMINI.en.md) | [日本語](GEMINI.ja.md) | [한국어](GEMINI.ko.md) | [Français](GEMINI.fr.md) | [Deutsch](GEMINI.de.md)

# Jarvis Projektkontext

Dieses Dokument stellt Gemini genaue Kontextinformationen zum `JARVIS` Monorepo zur Verfügung.

## Projektübersicht

**Name**: Jarvis AI-Assistent
**Architektur**: Multi-Service-Monorepo (FastAPI-Backend + Vue 3-Frontend)
**Zweck**: KI-Assistentenplattform mit RAG-Wissensbasis, Multi-LLM-Unterstützung und Streaming-Konversationen.

## Verzeichnisstruktur

```
JARVIS/
├── backend/          # FastAPI-Backend-Service (Python 3.13 + SQLAlchemy + LangGraph)
├── frontend/         # Vue 3-Frontend (Vite + TypeScript + Pinia)
├── docker-compose.yml
├── pyproject.toml    # Stammverzeichnis (nur Entwicklungstools, keine Laufzeitabhängigkeiten)
└── CLAUDE.md / GEMINI.md
```

## Backend-Architektur (backend/)

- **Framework**: FastAPI + Uvicorn
- **Datenbank**: PostgreSQL (asyncpg-Treiber) + SQLAlchemy async ORM + Alembic-Migrationen
- **Cache**: Redis
- **Vektorspeicher**: Qdrant (RAG-Wissensbasis)
- **Objektspeicher**: MinIO (Datei-Uploads)
- **LLM**: LangGraph + LangChain, unterstützt DeepSeek / OpenAI / Anthropic
- **Authentifizierung**: JWT (python-jose) + bcrypt (passlib)

### Hauptmodule

```
backend/app/
├── api/          # FastAPI-Routen (auth, conversations, documents, settings)
├── agent/        # LangGraph-Agent-Graph + LLM-Fabrik
├── core/         # Konfiguration (pydantic-settings), Datenbank, Sicherheitstools
├── models/       # SQLAlchemy ORM-Modelle
├── rag/          # Dokumentenanalyse, Chunking, Qdrant-Indexierung
└── main.py       # Anwendungseinstiegspunkt (CORS, Routenregistrierung, Gesundheitsprüfung)
```

## Frontend-Architektur (frontend/)

- **Framework**: Vue 3 + TypeScript + Vite
- **Zustandsverwaltung**: Pinia (auth store, chat store)
- **Routing**: Vue Router 4 (Lazy Loading + Route Guards)
- **UI**: Benutzerdefinierte CSS-Stile

## Umgebung und Abhängigkeiten

### Backend (mit uv)
```bash
cd backend
uv sync                          # Abhängigkeiten installieren
uv run uvicorn app.main:app --reload  # Entwicklungsserver
uv run pytest tests/ -v          # Tests ausführen
uv run alembic upgrade head      # Datenbankmigrationen ausführen
```

### Frontend (mit bun)
```bash
cd frontend
bun install                      # Abhängigkeiten installieren
bun run dev                      # Entwicklungsserver
bun run build                    # Produktions-Build
bun run lint                     # ESLint-Prüfung
bun run type-check               # TypeScript-Typprüfung
```

### Docker-Umgebung
```bash
docker-compose up -d             # Alle Dienste starten (PostgreSQL, Redis, Qdrant, MinIO, Backend, Frontend)
```

## Entwicklungsworkflow

### Branch-Strategie
- **main**: Stabile Version (Deployment-Branch)
- **dev**: Täglicher Entwicklungsbranch (alle Änderungen werden hier vorgenommen)
- `dev` nur bei ausdrücklicher Anweisung in `main` mergen

### Code-Qualitätstools

**Backend**:
- `ruff check --fix && ruff format`: Lint + Formatierung
- `mypy`: Typprüfung
- `pytest`: Tests

**Frontend**:
- `bun run lint`: ESLint-Prüfung
- `bun run type-check`: TypeScript-Typprüfung

**Vor dem Commit (Pre-Commit-Hooks laufen automatisch)**:
- YAML/TOML/JSON-Formatprüfung
- uv.lock-Synchronisierungsprüfung
- ruff lint + format
- Frontend ESLint + TypeScript-Typprüfung

## Wichtige Konfiguration

- **DATABASE_URL**: `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL**: `redis://localhost:6379`
- **JWT_SECRET**: Über Umgebungsvariable konfiguriert
- **DEEPSEEK_API_KEY**: Über Umgebungsvariable konfiguriert
- **Alembic-Migrationen**: Liest automatisch aus `DATABASE_URL` und konvertiert zum synchronen psycopg2-Treiber
