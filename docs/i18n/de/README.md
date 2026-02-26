[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](../fr/README.md) | [Deutsch](README.md)

# JARVIS

> Eine KI-Assistenzplattform mit RAG-Wissensdatenbank, Multi-LLM-Unterstützung und Echtzeit-Streaming-Konversationen — mit einer Dark-Luxury-Designsprache.

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## Funktionen

- **Multi-Modell-Unterstützung** — DeepSeek / OpenAI / Anthropic, pro Benutzer in den Einstellungen umschaltbar
- **RAG-Wissensdatenbank** — PDF / TXT / MD / DOCX hochladen mit automatischem Chunking und Vektorindexierung
- **Streaming-Chat** — SSE Token-für-Token-Ausgabe über LangGraph ReAct Agent
- **Dark Luxury UI** — Glassmorphismus-Karten, Gold-Verlaufseffekte, fließende Animationsübergänge
- **Mehrsprachig** — 6 Sprachen: Chinesisch / Englisch / Japanisch / Koreanisch / Französisch / Deutsch
- **Produktionsreife Infrastruktur** — 4-Schichten-Netzwerkisolierung, Traefik Edge-Router, Prometheus + Grafana Observability

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

## Voraussetzungen

| Tool | Version | Installation |
|------|---------|-------------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | aktuell | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **Nur für lokale Entwicklung** wird zusätzlich [Bun](https://bun.sh) für das Frontend benötigt.

## Schnellstart

### 1. Klonen und Umgebung generieren

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh
```

> Erfordert `uv` (wird intern zur Generierung des Fernet-Verschlüsselungsschlüssels verwendet). Keine weitere Einrichtung erforderlich.

### 2. LLM-API-Schlüssel eintragen

Öffnen Sie `.env` und tragen Sie mindestens einen Schlüssel ein:

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # optional
ANTHROPIC_API_KEY=sk-ant-... # optional
```

### 3. Starten

```bash
docker compose up -d
```

Beim ersten Start werden die Docker-Images gebaut — bitte einige Minuten einplanen. Sobald alles bereit ist:

| Dienst | URL | Verfügbarkeit |
|--------|-----|---------------|
| **App** | http://localhost | immer |
| Grafana (Monitoring) | http://localhost:3001 | immer |
| Traefik-Dashboard | http://localhost:8080/dashboard/ | nur Entwicklung |
| Backend-API (direkt) | http://localhost:8000 | nur Entwicklung |

> Das Standard-`docker compose up -d` führt `docker-compose.override.yml` automatisch zusammen, was Debug-Ports freilegt und Hot-Reload für den Backend-Code aktiviert. Für die Produktion siehe unten.

### Fehlerbehebung

**Dienste starten nicht** — Logs prüfen:
```bash
docker compose logs backend
docker compose logs traefik
```

**Komplett neu aufbauen** (nach Änderungen an Dockerfiles oder Abhängigkeiten):
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**Port-Konflikt auf `:80`** — Stoppen Sie, was Port 80 belegt, und versuchen Sie es erneut.

---

## Docker-Compose-Dateien

Dieses Projekt verwendet zwei Compose-Dateien, die zusammenarbeiten:

| Datei | Zweck |
|-------|-------|
| `docker-compose.yml` | **Basis (Produktion)** — minimale Oberfläche: nur `:80` und `:3001` freigelegt |
| `docker-compose.override.yml` | **Entwicklungs-Overrides** — wird automatisch von Docker Compose zusammengeführt; fügt Debug-Ports, Hot-Reload hinzu |

Docker Compose führt die Override-Datei automatisch zusammen, wenn Sie `docker compose up -d` ausführen, daher **sind für die lokale Entwicklung keine zusätzlichen Flags erforderlich**. Für die Produktion explizit ausschließen:

```bash
# Entwicklung (Standard) — beide Dateien werden automatisch zusammengeführt
docker compose up -d

# Produktion — nur Basisdatei, keine Debug-Ports, kein Hot-Reload
docker compose -f docker-compose.yml up -d
```

## Produktions-Deployment

```bash
docker compose -f docker-compose.yml up -d
```

Freigegebene Ports: nur `:80` (App) und `:3001` (Grafana).

---

## Lokale Entwicklung

Backend und Frontend nativ ausführen für schnellere Iteration.

**Schritt 1 — Infrastruktur starten:**

```bash
docker compose up -d postgres redis qdrant minio
```

**Schritt 2 — Backend** (neues Terminal, vom Repo-Wurzelverzeichnis):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**Schritt 3 — Frontend** (neues Terminal, vom Repo-Wurzelverzeichnis):

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173  (leitet /api → localhost:8000 weiter)
```

---

## Projektstruktur

```
JARVIS/
├── backend/                    # FastAPI (Python 3.13 + uv)
│   ├── app/
│   │   ├── agent/              # LangGraph ReAct Agent
│   │   ├── api/                # HTTP-Routen (auth/chat/conversations/documents/settings)
│   │   ├── core/               # Konfiguration, JWT/bcrypt/Fernet-Sicherheit, Rate Limiting
│   │   ├── db/                 # SQLAlchemy async Modelle + Sessions
│   │   ├── infra/              # Qdrant / MinIO / Redis Singletons
│   │   ├── rag/                # Dokument-Chunker + Embedder + Indexer
│   │   └── tools/              # LangGraph-Tools (search/code_exec/file/datetime)
│   ├── alembic/                # Datenbankmigrationen
│   └── tests/                  # pytest-Suite
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Axios-Singleton + Auth-Interceptor
│       ├── stores/             # Pinia-Stores (auth + chat)
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n (zh/en/ja/ko/fr/de)
├── database/                   # Docker-Initialisierungsskripte (postgres/redis/qdrant)
├── monitoring/                 # Prometheus-Konfiguration + Grafana-Provisioning
├── traefik/                    # Traefik dynamische Routing-Konfiguration
├── scripts/
│   └── init-env.sh             # Generiert sichere .env (erfordert uv)
├── docker-compose.yml          # Basis-Orchestrierung
├── docker-compose.override.yml # Entwicklungs-Overrides (Debug-Ports + Hot-Reload)
└── .env.example                # Umgebungsvariablen-Referenz
```

---

## Entwicklung

### Codequalität

```bash
# Backend (aus backend/ ausführen)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# Frontend (aus frontend/ ausführen)
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# Vom Repo-Wurzelverzeichnis ausführen
pre-commit install
pre-commit run --all-files
```

Hooks: YAML/TOML/JSON-Validierung · uv.lock-Synchronisation · Ruff lint+format · ESLint · mypy · vue-tsc · gitleaks Secret-Scanning · direkte Commits auf `main` blockieren.

---

## Umgebungsvariablen

`bash scripts/init-env.sh` generiert alle Zugangsdaten automatisch. Sie müssen nur einen LLM-API-Schlüssel angeben.

| Variable | Beschreibung |
|----------|-------------|
| `POSTGRES_PASSWORD` | PostgreSQL-Passwort |
| `MINIO_ROOT_USER/PASSWORD` | MinIO-Objektspeicher-Zugangsdaten |
| `REDIS_PASSWORD` | Redis-Authentifizierungspasswort |
| `JWT_SECRET` | JWT-Signierschlüssel |
| `ENCRYPTION_KEY` | Fernet-Schlüssel zur Verschlüsselung von Benutzer-API-Schlüsseln im Ruhezustand |
| `GRAFANA_PASSWORD` | Grafana-Admin-Passwort |
| `DEEPSEEK_API_KEY` | **Manuell eintragen** |
| `OPENAI_API_KEY` | Optional |
| `ANTHROPIC_API_KEY` | Optional |

Vollständige Referenz finden Sie in `.env.example`.

---

## Mitwirken

Siehe [CONTRIBUTING.md](../../../.github/CONTRIBUTING.md).

## Lizenz

[MIT](../../../LICENSE)
