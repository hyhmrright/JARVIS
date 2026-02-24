[中文](../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# JARVIS

Plateforme d'assistant IA avec base de connaissances RAG, support multi-LLM et conversations en streaming.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | FastAPI · LangGraph · SQLAlchemy · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| Base de données | PostgreSQL · Redis · Qdrant (base vectorielle) |
| Stockage | MinIO |
| LLM | DeepSeek · OpenAI · Anthropic |

## Structure du projet

```
JARVIS/
├── backend/          # Backend FastAPI (Python 3.13 + uv)
├── frontend/         # Frontend Vue 3 (Bun)
├── docker-compose.yml
└── pyproject.toml    # Configuration des outils de développement (racine)
```

## Démarrage rapide

### Lancement full-stack (recommandé)

Copiez et remplissez le fichier de variables d'environnement, puis lancez :

```bash
cp .env.example .env   # Remplissez vos secrets
docker compose up -d
```

Adresses des services : Frontend http://localhost:3000 · Backend http://localhost:8000

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
uv run pyright
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

Créez un fichier `.env` à la racine du projet :

```env
# Base de données
POSTGRES_PASSWORD=your_password

# Stockage objet
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# Authentification
JWT_SECRET=your_jwt_secret

# LLM (fournisseur par défaut ; les clés API des autres fournisseurs sont configurées par utilisateur via la page de paramètres)
DEEPSEEK_API_KEY=your_key
```

Pour le développement local, le backend nécessite également `backend/.env` pour se connecter aux services locaux :

```env
DATABASE_URL=postgresql+asyncpg://jarvis:your_password@localhost:5432/jarvis
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
JWT_SECRET=your_jwt_secret
# Clé de chiffrement Fernet (utilisée pour chiffrer les clés API des utilisateurs)
# Génération : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key
DEEPSEEK_API_KEY=your_key
```
