[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](README.md) | [Deutsch](../de/README.md)

# JARVIS

Plateforme d'assistant IA avec base de connaissances RAG, support multi-LLM et conversations en streaming. Conçue avec un design Dark Luxury pour une expérience d'interaction IA haut de gamme.

## Fonctionnalités

- **Support multi-modèles** — DeepSeek / OpenAI / Anthropic, librement interchangeables dans les paramètres
- **Base de connaissances RAG** — Téléchargement de documents (PDF/TXT/MD/DOCX) avec découpage automatique et stockage vectoriel
- **Chat en streaming** — Sortie SSE en temps réel, affichage des réponses IA token par token
- **LangGraph Agent** — Architecture en boucle ReAct avec appels d'outils pour l'exécution de code, les opérations de fichiers, etc.
- **UI Dark Luxury** — Cartes en glassmorphisme, accents en dégradé doré, transitions animées raffinées
- **Multilingue** — Supporte 6 langues : chinois / anglais / japonais / coréen / français / allemand
- **Docker production** — Isolation réseau à 4 couches, routeur edge Traefik, stack d'observabilité complète

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Base de données | PostgreSQL · Redis · Qdrant (base vectorielle) |
| Stockage | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |
| Routeur edge | Traefik v3 |
| Observabilité | Prometheus · Grafana · cAdvisor |
| Design | Système de design CSS Variables · Glassmorphisme · Thème sombre |

## Structure du projet

```
JARVIS/
├── backend/           # Backend FastAPI (Python 3.13 + uv)
│   ├── app/           # Code applicatif (agent/api/core/db/infra/rag/tools)
│   ├── alembic/       # Migrations de base de données
│   └── tests/         # Suite de tests pytest
├── frontend/          # Frontend Vue 3 (Bun)
│   └── src/
│       ├── assets/styles/  # Système de design CSS (global/animations/components)
│       ├── pages/          # Composants de page (Login/Register/Chat/Documents/Settings)
│       ├── stores/         # Gestion d'état Pinia
│       └── locales/        # i18n multilingue
├── database/          # Scripts d'initialisation Docker (postgres/redis/qdrant)
├── monitoring/        # Configuration Prometheus + provisionnement Grafana
├── traefik/           # Configuration du routage dynamique Traefik
├── docker-compose.yml          # Orchestration production (réseaux à 4 couches)
├── docker-compose.override.yml # Surcharges dev (ports exposés, rechargement à chaud)
└── pyproject.toml     # Configuration des outils de développement (racine)
```

## Démarrage rapide

### Lancement full-stack (recommandé)

Générez le fichier de variables d'environnement, puis lancez :

```bash
bash scripts/init-env.sh   # Génère automatiquement un .env sécurisé (première fois)
docker compose up -d
```

| Service | URL |
|---------|-----|
| **Application (via Traefik)** | http://localhost |
| Grafana (monitoring) | http://localhost:3001 |
| Tableau de bord Traefik | http://localhost:8080/dashboard/ |

> Reconstruction sans cache : `docker compose down && docker compose build --no-cache && docker compose up -d --force-recreate`

### Développement local

**Prérequis :** Docker (pour les services d'infrastructure), Python 3.13+, [uv](https://github.com/astral-sh/uv), [Bun](https://bun.sh)

```bash
# Démarrer les services d'infrastructure
docker compose up -d postgres redis qdrant minio

# Backend
cd backend
uv sync
uv run alembic upgrade head           # Exécuter les migrations de base de données
uv run uvicorn app.main:app --reload  # Serveur de développement (:8000)

# Frontend (nouveau terminal)
cd frontend
bun install
bun run dev                           # Serveur de développement (:5173)
```

## Développement

### Qualité du code

```bash
# Backend (dans le répertoire backend/)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# Frontend (dans le répertoire frontend/)
bun run lint
bun run type-check
```

### Pre-commit Hooks

```bash
pre-commit install         # Installer les git hooks (exécuter à la racine)
pre-commit run --all-files
```

## Variables d'environnement

Exécutez `bash scripts/init-env.sh` pour générer automatiquement un `.env` sécurisé avec des mots de passe et clés aléatoires.

Le script configure : `POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `GRAFANA_PASSWORD`, `DATABASE_URL`, `REDIS_URL`.

Seul `DEEPSEEK_API_KEY` doit être renseigné manuellement. Voir `.env.example` pour plus de détails.
