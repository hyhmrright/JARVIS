[中文](../../../GEMINI.md) | [English](GEMINI.en.md) | [日本語](GEMINI.ja.md) | [한국어](GEMINI.ko.md) | [Français](GEMINI.fr.md) | [Deutsch](GEMINI.de.md)

# Contexte du projet Jarvis

Ce document fournit à Gemini des informations de contexte précises sur le monorepo `JARVIS`.

## Aperçu du projet

**Nom** : Jarvis AI Assistant
**Architecture** : Monorepo multi-services (backend FastAPI + frontend Vue 3)
**Objectif** : Plateforme d'assistant IA avec base de connaissances RAG, support multi-LLM et conversations en streaming.

## Structure des répertoires

```
JARVIS/
├── backend/          # Service backend FastAPI (Python 3.13 + SQLAlchemy + LangGraph)
├── frontend/         # Frontend Vue 3 (Vite + TypeScript + Pinia)
├── docker-compose.yml
├── pyproject.toml    # Répertoire racine (outils de développement uniquement, pas de dépendances d'exécution)
└── CLAUDE.md / GEMINI.md
```

## Architecture backend (backend/)

- **Framework** : FastAPI + Uvicorn
- **Base de données** : PostgreSQL (pilote asyncpg) + SQLAlchemy async ORM + migrations Alembic
- **Cache** : Redis
- **Stockage vectoriel** : Qdrant (base de connaissances RAG)
- **Stockage objet** : MinIO (téléchargement de fichiers)
- **LLM** : LangGraph + LangChain, supportant DeepSeek / OpenAI / Anthropic
- **Authentification** : JWT (python-jose) + bcrypt (passlib)

### Modules principaux

```
backend/app/
├── api/          # Routes FastAPI (auth, conversations, documents, settings)
├── agent/        # Graphe d'agent LangGraph + fabrique LLM
├── core/         # Configuration (pydantic-settings), base de données, utilitaires de sécurité
├── models/       # Modèles ORM SQLAlchemy
├── rag/          # Analyse de documents, découpage, indexation Qdrant
└── main.py       # Point d'entrée de l'application (CORS, enregistrement des routes, vérification de santé)
```

## Architecture frontend (frontend/)

- **Framework** : Vue 3 + TypeScript + Vite
- **Gestion d'état** : Pinia (auth store, chat store)
- **Routage** : Vue Router 4 (chargement paresseux + gardes de route)
- **UI** : Styles CSS personnalisés

## Environnement et dépendances

### Backend (avec uv)
```bash
cd backend
uv sync                          # Installer les dépendances
uv run uvicorn app.main:app --reload  # Serveur de développement
uv run pytest tests/ -v          # Exécuter les tests
uv run alembic upgrade head      # Exécuter les migrations de base de données
```

### Frontend (avec bun)
```bash
cd frontend
bun install                      # Installer les dépendances
bun run dev                      # Serveur de développement
bun run build                    # Build de production
bun run lint                     # Vérification ESLint
bun run type-check               # Vérification de types TypeScript
```

### Environnement Docker
```bash
docker-compose up -d             # Démarrer tous les services (PostgreSQL, Redis, Qdrant, MinIO, backend, frontend)
```

## Flux de travail de développement

### Stratégie de branches
- **main** : Version stable (branche de déploiement)
- **dev** : Branche de développement quotidien (toutes les modifications sont effectuées ici)
- Ne fusionner `dev` dans `main` que sur instruction explicite

### Outils de qualité du code

**Backend** :
- `ruff check --fix && ruff format` : Lint + formatage
- `mypy` : Vérification de types
- `pytest` : Tests

**Frontend** :
- `bun run lint` : Vérification ESLint
- `bun run type-check` : Vérification de types TypeScript

**Avant le commit (les hooks pré-commit s'exécutent automatiquement)** :
- Vérification du format YAML/TOML/JSON
- Vérification de synchronisation uv.lock
- ruff lint + format
- Frontend ESLint + vérification de types TypeScript

## Configuration clé

- **DATABASE_URL** : `postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis`
- **REDIS_URL** : `redis://localhost:6379`
- **JWT_SECRET** : Configuré via variable d'environnement
- **DEEPSEEK_API_KEY** : Configuré via variable d'environnement
- **Migrations Alembic** : Lit automatiquement depuis `DATABASE_URL` et convertit en pilote synchrone psycopg2
