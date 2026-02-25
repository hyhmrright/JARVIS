[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](README.md)

# JARVIS

KI-Assistenzplattform mit RAG-Wissensdatenbank, Multi-LLM-Unterstützung und Streaming-Konversationen. Mit einem Dark-Luxury-Design für ein erstklassiges KI-Interaktionserlebnis.

## Funktionen

- **Multi-Modell-Unterstützung** — DeepSeek / OpenAI / Anthropic, frei umschaltbar in den Einstellungen
- **RAG-Wissensdatenbank** — Dokumente hochladen (PDF/TXT/MD/DOCX) mit automatischem Chunking und Vektorspeicherung
- **Streaming-Chat** — SSE-Echtzeit-Streaming-Ausgabe, KI-Antworten Token für Token anzeigen
- **LangGraph Agent** — ReAct-Schleifenarchitektur mit Tool-Aufrufen für Codeausführung, Dateioperationen und mehr
- **Dark Luxury UI** — Glassmorphismus-Karten, Gold-Verlaufseffekte, feine Animationsübergänge
- **Mehrsprachig** — Unterstützt 6 Sprachen: Chinesisch / Englisch / Japanisch / Koreanisch / Französisch / Deutsch
- **Produktionsreifes Docker** — 4-Schichten-Netzwerkisolierung, Traefik Edge-Router, vollständiger Observability-Stack

## Technologie-Stack

| Schicht | Technologie |
|---------|-------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Datenbank | PostgreSQL · Redis · Qdrant (Vektordatenbank) |
| Speicher | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| Edge-Router | Traefik v3 |
| Observability | Prometheus · Grafana · cAdvisor |
| Design | CSS Variables Designsystem · Glassmorphismus · Dunkles Thema |

## Projektstruktur

```
JARVIS/
├── backend/           # FastAPI-Backend (Python 3.13 + uv)
│   ├── app/           # Anwendungscode (agent/api/core/db/infra/rag/tools)
│   ├── alembic/       # Datenbankmigrationen
│   └── tests/         # pytest-Testsuite
├── frontend/          # Vue 3-Frontend (Bun)
│   └── src/
│       ├── assets/styles/  # CSS-Designsystem (global/animations/components)
│       ├── pages/          # Seitenkomponenten (Login/Register/Chat/Documents/Settings)
│       ├── stores/         # Pinia-Zustandsverwaltung
│       └── locales/        # i18n Mehrsprachigkeit
├── database/          # Docker-Initialisierungsskripte (postgres/redis/qdrant)
├── monitoring/        # Prometheus-Konfiguration + Grafana-Provisioning
├── traefik/           # Traefik dynamische Routing-Konfiguration
├── docker-compose.yml          # Produktions-Orchestrierung (4-Schichten-Netzwerke)
├── docker-compose.override.yml # Entwicklungs-Overrides (Ports, Hot-Reload)
└── pyproject.toml     # Entwicklungswerkzeug-Konfiguration (Wurzelverzeichnis)
```

## Schnellstart

### Full-Stack-Start (empfohlen)

Generieren Sie die Umgebungsvariablen-Datei und starten Sie:

```bash
bash scripts/init-env.sh   # Sichere .env automatisch generieren (nur beim ersten Mal)
docker compose up -d
```

| Dienst | URL |
|--------|-----|
| **Anwendung (über Traefik)** | http://localhost |
| Grafana (Monitoring) | http://localhost:3001 |
| Traefik-Dashboard | http://localhost:8080/dashboard/ |

> Neuaufbau ohne Cache: `docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

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
uv run mypy app
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

Das Skript konfiguriert: `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `GRAFANA_PASSWORD`, `DATABASE_URL`, `REDIS_URL`.

Nur `DEEPSEEK_API_KEY` muss manuell eingetragen werden. Details finden Sie in `.env.example`.
