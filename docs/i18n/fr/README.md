[English](../../../README.md) | [中文](../zh/README.md) | [日本語](../ja/README.md) | [한국어](../ko/README.md) | [Français](README.md) | [Deutsch](../de/README.md)

# JARVIS

> Une plateforme d'assistant IA avec base de connaissances RAG, support multi-LLM et conversations en streaming en temps réel — avec un langage de design Dark Luxury.

![License](https://img.shields.io/github/license/hyhmrright/JARVIS)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Vue](https://img.shields.io/badge/vue-3-brightgreen)

## Fonctionnalités

- **Support multi-modèles** — DeepSeek / OpenAI / Anthropic, commutable par utilisateur dans les Paramètres
- **Base de connaissances RAG** — Importez des fichiers PDF / TXT / MD / DOCX avec découpage automatique et indexation vectorielle
- **Chat en streaming** — Sortie SSE token par token via l'agent LangGraph ReAct
- **UI Dark Luxury** — Cartes en glassmorphisme, accents en dégradé doré, transitions animées fluides
- **Multilingue** — 6 langues : chinois / anglais / japonais / coréen / français / allemand
- **Infrastructure production** — Isolation réseau à 4 couches, routeur edge Traefik, observabilité Prometheus + Grafana

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

## Prérequis

| Outil | Version | Installation |
|-------|---------|--------------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **Le développement local uniquement** nécessite en plus [Bun](https://bun.sh) pour le frontend.

## Démarrage rapide

### 1. Cloner et générer l'environnement

```bash
git clone https://github.com/hyhmrright/JARVIS.git
cd JARVIS
bash scripts/init-env.sh
```

> Nécessite `uv` (utilisé en interne pour générer la clé de chiffrement Fernet). Aucune autre configuration requise.

### 2. Ajouter votre clé API LLM

Ouvrez `.env` et renseignez au moins une clé :

```
DEEPSEEK_API_KEY=sk-...      # https://platform.deepseek.com
OPENAI_API_KEY=sk-...        # optionnel
ANTHROPIC_API_KEY=sk-ant-... # optionnel
```

### 3. Démarrer

```bash
docker compose up -d
```

La première exécution construit les images Docker — prévoyez quelques minutes. Une fois opérationnel :

| Service | URL | Disponible |
|---------|-----|------------|
| **Application** | http://localhost | toujours |
| Grafana (monitoring) | http://localhost:3001 | toujours |
| Tableau de bord Traefik | http://localhost:8080/dashboard/ | dev uniquement |
| API Backend (direct) | http://localhost:8000 | dev uniquement |

> La commande `docker compose up -d` par défaut fusionne automatiquement `docker-compose.override.yml`, ce qui expose les ports de débogage et active le rechargement à chaud du code backend. Pour la production, voir ci-dessous.

### Dépannage

**Les services ne démarrent pas** — vérifiez les journaux :
```bash
docker compose logs backend
docker compose logs traefik
```

**Reconstruction complète** (après modification des Dockerfiles ou des dépendances) :
```bash
docker compose down
docker compose build --no-cache
docker compose up -d --force-recreate
```

**Conflit de port sur `:80`** — arrêtez ce qui occupe le port 80, puis réessayez.

---

## Fichiers Docker Compose

Ce projet utilise deux fichiers compose qui fonctionnent ensemble :

| Fichier | Rôle |
|---------|------|
| `docker-compose.yml` | **Base (production)** — surface minimale : seuls `:80` et `:3001` exposés |
| `docker-compose.override.yml` | **Surcharges dev** — fusionné automatiquement par Docker Compose ; ajoute les ports de débogage et le rechargement à chaud |

Docker Compose fusionne automatiquement le fichier override lorsque vous exécutez `docker compose up -d`, donc **aucun indicateur supplémentaire n'est nécessaire pour le développement local**. Pour la production, excluez-le explicitement :

```bash
# Développement (par défaut) — fusionne les deux fichiers automatiquement
docker compose up -d

# Production — fichier de base uniquement, sans ports de débogage ni rechargement à chaud
docker compose -f docker-compose.yml up -d
```

## Déploiement en production

```bash
docker compose -f docker-compose.yml up -d
```

Ports exposés : `:80` (application) et `:3001` (Grafana) uniquement.

---

## Développement local

Exécutez le backend et le frontend en natif pour une itération plus rapide.

**Étape 1 — démarrer l'infrastructure :**

```bash
docker compose up -d postgres redis qdrant minio
```

**Étape 2 — backend** (nouveau terminal, depuis la racine du dépôt) :

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

**Étape 3 — frontend** (nouveau terminal, depuis la racine du dépôt) :

```bash
cd frontend
bun install
bun run dev   # http://localhost:5173  (proxie /api → localhost:8000)
```

---

## Structure du projet

```
JARVIS/
├── backend/                    # FastAPI (Python 3.13 + uv)
│   ├── app/
│   │   ├── agent/              # Agent LangGraph ReAct
│   │   ├── api/                # Routes HTTP (auth/chat/conversations/documents/settings)
│   │   ├── core/               # Config, sécurité JWT/bcrypt/Fernet, limitation de débit
│   │   ├── db/                 # Modèles async SQLAlchemy + sessions
│   │   ├── infra/              # Singletons Qdrant / MinIO / Redis
│   │   ├── rag/                # Découpeur + embedder + indexeur de documents
│   │   └── tools/              # Outils LangGraph (search/code_exec/file/datetime)
│   ├── alembic/                # Migrations de base de données
│   └── tests/                  # Suite pytest
├── frontend/                   # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/                # Singleton Axios + intercepteur d'auth
│       ├── stores/             # Stores Pinia (auth + chat)
│       ├── pages/              # Login / Register / Chat / Documents / Settings
│       └── locales/            # i18n (zh/en/ja/ko/fr/de)
├── database/                   # Scripts d'initialisation Docker (postgres/redis/qdrant)
├── monitoring/                 # Config Prometheus + provisionnement Grafana
├── traefik/                    # Config de routage dynamique Traefik
├── scripts/
│   └── init-env.sh             # Génère un .env sécurisé (nécessite uv)
├── docker-compose.yml          # Orchestration de base
├── docker-compose.override.yml # Surcharges dev (ports de débogage + rechargement à chaud)
└── .env.example                # Référence des variables d'environnement
```

---

## Développement

### Qualité du code

```bash
# Backend (exécuter depuis backend/)
uv run ruff check --fix && uv run ruff format
uv run mypy app
uv run pytest tests/ -v

# Frontend (exécuter depuis frontend/)
bun run lint:fix
bun run type-check
```

### Pre-commit Hooks

```bash
# Exécuter depuis la racine du dépôt
pre-commit install
pre-commit run --all-files
```

Hooks : validation YAML/TOML/JSON · synchronisation uv.lock · Ruff lint+format · ESLint · mypy · vue-tsc · analyse des secrets gitleaks · blocage des commits directs sur `main`.

---

## Variables d'environnement

`bash scripts/init-env.sh` génère automatiquement tous les identifiants. Vous n'avez besoin de fournir qu'une clé API LLM.

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL |
| `MINIO_ROOT_USER/PASSWORD` | Identifiants de stockage objet MinIO |
| `REDIS_PASSWORD` | Mot de passe d'authentification Redis |
| `JWT_SECRET` | Secret de signature JWT |
| `ENCRYPTION_KEY` | Clé Fernet pour le chiffrement des clés API utilisateur au repos |
| `GRAFANA_PASSWORD` | Mot de passe administrateur Grafana |
| `DEEPSEEK_API_KEY` | **À renseigner manuellement** |
| `OPENAI_API_KEY` | Optionnel |
| `ANTHROPIC_API_KEY` | Optionnel |

Consultez `.env.example` pour la référence complète.

---

## Contribuer

Voir [CONTRIBUTING.md](../../../.github/CONTRIBUTING.md).

## Licence

[MIT](../../../LICENSE)
