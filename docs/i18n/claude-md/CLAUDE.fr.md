[中文](../../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

Ce fichier fournit des directives pour Claude Code lorsqu'il travaille dans cette base de code.

## Stratégie de branches

- **main** : Utilisé uniquement pour les releases. Les commits directs ou le développement sont interdits. Seuls les merges depuis dev ou d'autres branches de développement sont acceptés.
- **dev** : Branche de développement principale. Tout le développement quotidien, les corrections de bugs et le développement de fonctionnalités se font sur cette branche ou ses sous-branches.
- Après le développement : dev → merge → main → push. Aucune étape ne peut être ignorée.

## Aperçu du projet

JARVIS est une plateforme d'assistant IA dotée d'une base de connaissances RAG, d'un support multi-LLM et de conversations en streaming, utilisant une structure monorepo.

## Architecture principale

```
JARVIS/
├── backend/           # Backend FastAPI (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # Point d'entrée FastAPI, lifespan gère les connexions infra
│   │   ├── agent/     # Agent ReAct LangGraph (graph/llm/state)
│   │   ├── api/       # Routes HTTP (auth/chat/conversations/documents/settings)
│   │   ├── core/      # Config (Pydantic Settings), sécurité (JWT/bcrypt/Fernet), limitation de débit
│   │   ├── db/        # Modèles et sessions async SQLAlchemy
│   │   ├── infra/     # Singletons clients d'infrastructure (Qdrant/MinIO/Redis)
│   │   ├── rag/       # Pipeline RAG (chunker/embedder/indexer)
│   │   └── tools/     # Outils LangGraph (search/code_exec/file/datetime)
│   ├── alembic/       # Migrations de base de données
│   └── tests/         # Suite de tests pytest
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/       # Singleton Axios + intercepteur auth
│       ├── stores/    # Stores Pinia (auth + chat)
│       ├── pages/     # Composants de pages (Login/Register/Chat/Documents/Settings)
│       ├── locales/   # i18n (zh/en/ja/ko/fr/de)
│       └── router/    # Vue Router + garde auth
├── database/          # Scripts d'initialisation Docker (postgres/redis/qdrant)
├── docker-compose.yml # Orchestration full-stack
└── pyproject.toml     # Config outils de dev racine (ruff/pyright/pre-commit), pas de deps runtime
```

### Points clés de l'architecture backend

**Agent LLM** : `agent/graph.py` implémente une boucle ReAct en utilisant `StateGraph` de LangGraph (llm → tools → llm → END). Une nouvelle instance de graphe est créée par requête, sans persistance de checkpoint. La factory LLM (`agent/llm.py`) distribue via `match/case` vers `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`.

**Chat en streaming** : `POST /api/chat/stream` dans `api/chat.py` retourne un SSE `StreamingResponse`. Note : le générateur de streaming utilise une session `AsyncSessionLocal` séparée en interne (la session au niveau de la requête se ferme quand le handler retourne et ne peut pas être réutilisée).

**Pipeline RAG** : Upload de document → `extract_text()` → `chunk_text()` (fenêtre glissante, 500 mots/50 mots de chevauchement) → `OpenAIEmbeddings` (text-embedding-3-small, 1536 dimensions) → Qdrant upsert. Une collection par utilisateur (`user_{id}`). Note : la recherche RAG n'est pas encore connectée au flux de conversation de l'agent.

**Modèles de base de données** : 5 tables — `users`, `user_settings` (JSONB stocke les clés API chiffrées Fernet), `conversations`, `messages` (immuable), `documents` (suppression douce). Toutes utilisent des clés primaires UUID.

**Singletons d'infrastructure** : Qdrant utilise un global au niveau module + initialisation paresseuse + asyncio.Lock ; MinIO utilise `@lru_cache` + `asyncio.to_thread()` (SDK synchrone) ; PostgreSQL utilise engine + sessionmaker au niveau module.

### Points clés de l'architecture frontend

**Gestion d'état** : Deux stores Pinia — `auth.ts` (token JWT persisté dans localStorage) et `chat.ts` (liste de conversations + messages SSE en streaming). SSE utilise `fetch` natif + `ReadableStream` au lieu d'Axios (Axios ne supporte pas les corps de réponse en streaming).

**Routage** : 5 routes, tous les composants de page sont chargés paresseusement. Le garde `beforeEach` vérifie `auth.isLoggedIn`.

**Client API** : Instance Axios avec `baseURL: "/api"`, l'intercepteur de requête lit le token depuis localStorage. Le serveur de dev proxy `/api` → `http://backend:8000`.

**Internationalisation** : vue-i18n, 6 langues, priorité de détection : localStorage → navigator.language → zh.

## Environnement de développement

- **Python** : 3.13 (`.python-version`)
- **Gestionnaires de paquets** : Backend `uv`, Frontend `bun`
- **Environnement virtuel** : `.venv` (géré automatiquement par uv)

## Commandes courantes

### Configuration de l'environnement
```bash
bash scripts/init-env.sh             # Première exécution, génère .env (avec mots de passe/clés aléatoires)
uv sync                              # Installer les dépendances Python
cd frontend && bun install            # Installer les dépendances frontend
pre-commit install                    # Installer les git hooks
```

### Lancement de l'application
```bash
# Démarrer uniquement les services d'infrastructure (pour le dev local)
docker compose up -d postgres redis qdrant minio

# Backend (dans le répertoire backend/)
uv run alembic upgrade head           # Migration de base de données
uv run uvicorn app.main:app --reload  # Serveur de dev :8000

# Frontend (dans le répertoire frontend/)
bun run dev                           # Serveur de dev :5173 (proxy /api → backend:8000)

# Full-stack Docker
docker compose up -d                  # Frontend :3000 · Backend :8000
```

### Qualité du code
```bash
# Backend
ruff check                   # Lint
ruff check --fix             # Lint + correction automatique
ruff format                  # Formatage
pyright                      # Vérification des types

# Frontend (dans le répertoire frontend/)
bun run lint                 # ESLint
bun run lint:fix             # ESLint + correction automatique
bun run format               # Prettier
bun run type-check           # vue-tsc
```

### Tests
```bash
# Exécuter dans le répertoire backend/
uv run pytest tests/ -v                        # Tous les tests
uv run pytest tests/api/test_auth.py -v        # Fichier unique
uv run pytest tests/api/test_auth.py::test_login -v  # Cas de test unique
```

### Pre-commit Hooks
```bash
pre-commit run --all-files   # Exécuter manuellement tous les hooks
```

Les hooks incluent : vérifications de format YAML/TOML/JSON, synchronisation uv.lock, Ruff lint+format, ESLint, Pyright, vérification de types vue-tsc, scan de secrets gitleaks, blocage des commits directs sur main.

### Gestion des dépendances
```bash
# Python (le pyproject.toml racine gère les outils de dev, backend/pyproject.toml gère les deps runtime)
uv add <paquet>              # Ajouter une dépendance (exécuter dans le répertoire approprié)
uv add --group dev <paquet>  # Ajouter une dépendance de développement
uv lock                      # Régénérer le lock après modification manuelle de pyproject.toml

# Frontend
cd frontend && bun add <paquet>
```

## Configuration des outils

- **Ruff** : line-length=88, target-version="py313", quote-style="double"
- **Pyright** : typeCheckingMode="basic"
- **ESLint** : flat config, typescript-eslint + eslint-plugin-vue + prettier
- **TypeScript** : strict, bundler resolution, `@/*` → `src/*`

## Variables d'environnement

Toute configuration sensible (mot de passe de base de données, secret JWT, clé de chiffrement, identifiants MinIO) n'a pas de valeur par défaut et doit être fournie via `.env` ou des variables d'environnement. Exécutez `bash scripts/init-env.sh` pour la génération automatique. Seul `DEEPSEEK_API_KEY` nécessite une saisie manuelle.

---

# Règles de développement globales

## Auto-vérification avant les opérations Git

**Avant chaque `git commit`, `git push` ou appel de skill commit/push, une auto-vérification est obligatoire :**

```
Des fichiers ont-ils été modifiés dans cette session ?
   → Oui → La boucle qualité (simplifier → commit → review) a-t-elle été entièrement complétée ?
            → Non → [STOP] Exécuter immédiatement la boucle qualité
            → Oui → Continuer l'opération git
   → Non → Y a-t-il des modifications non commitées dans l'arbre de travail ? (git diff / git diff --cached / git stash list)
            → Oui (y compris stash) → [STOP] La boucle qualité complète doit d'abord être exécutée
            → Non → Continuer l'opération git
```

---

## Workflow obligatoire pour les modifications de code

### Référence des outils

| Outil | Type | Méthode d'appel | Moment d'exécution |
|-------|------|-----------------|-------------------|
| code-simplifier | Task agent | Outil `Task`, `subagent_type: "code-simplifier:code-simplifier"` | Avant le commit |
| Revue de code pré-push | Skill | `Skill: superpowers:requesting-code-review` | Après le commit, avant le push |
| Revue de code PR | Skill | `Skill: code-review:code-review --comment` | Après le push (nécessite une PR existante) |

### Conditions de déclenchement (une seule suffit)

- Un fichier a été modifié avec Edit / Write / NotebookEdit
- L'utilisateur a l'intention de persister les changements dans Git ou de pousser vers le remote (y compris les expressions comme "synchroniser", "télécharger", "créer une PR", "archiver", "ship", etc.)
- Sur le point d'invoquer un skill lié à commit / push

### Étapes d'exécution (ordre fixe, impossible à ignorer)

```
Écrire du code / Modifier des fichiers
      ↓
╔══════════════════ Boucle qualité (répéter jusqu'à absence de problèmes) ══════════════════╗
║                                                                                           ║
║  A. [OBLIGATOIRE] Task: code-simplifier                                                   ║
║     (Task agent, modifie directement les fichiers)                                        ║
║          ↓                                                                                ║
║  B. git add + commit                                                                      ║
║     Première entrée → git commit                                                          ║
║     Ré-entrée après correction → git commit --amend (garder l'historique propre pré-push) ║
║          ↓                                                                                ║
║  C. [OBLIGATOIRE] Skill: superpowers:requesting-code-review                               ║
║     (Fournir BASE_SHA=HEAD~1, HEAD_SHA=HEAD)                                              ║
║          ↓                                                                                ║
║     Problèmes trouvés ?                                                                   ║
║       Oui → Corriger le code ─────────────────────────→ Retour à l'étape A                ║
║       Non ↓                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════════════════╝
      ↓
git push (exécuter immédiatement, ne pas retarder)
      ↓ (si une GitHub PR existe)
[OBLIGATOIRE] Skill: code-review:code-review --comment
```

**Notes importantes :**
- La boucle qualité doit être entièrement exécutée (A→B→C) et C ne doit révéler aucun problème avant de sortir
- Utiliser `--amend` lors de la ré-entrée dans la boucle après corrections (maintenir un seul commit avant le push)
- `--amend` n'est pas une raison pour ignorer la revue ; C doit toujours être ré-exécuté

---

## Excuses courantes pour ignorer le workflow (toutes interdites)

Les raisons suivantes **ne doivent pas** être utilisées pour ignorer le workflow :

| Excuse | Action correcte |
|--------|----------------|
| "C'est juste un simple changement d'une ligne" | Doit être exécuté quelle que soit la taille du changement |
| "L'utilisateur a seulement dit commit, pas review" | Le commit lui-même est une condition de déclenchement |
| "Je viens de revoir un code similaire" | Doit être ré-exécuté après chaque changement |
| "C'est un fichier de test / documentation, pas la logique principale" | S'applique dès lors que Edit/Write a été utilisé pour modifier des fichiers |
| "Il faut push avant de review" | La review doit précéder le push |
| "L'utilisateur est pressé, commitons d'abord" | Le workflow n'est pas ignoré en raison de l'urgence |
| "Je connais très bien ce code" | La familiarité n'affecte pas les exigences du workflow |
| "Ces changements n'ont pas été faits dans cette session" | Doit être exécuté tant qu'il y a des changements non commités |
| "L'utilisateur n'a pas utilisé le mot 'commit'" | Se déclenche dès que l'intention est de commiter/pousser |
| "C'est un --amend, pas un nouveau commit" | --amend modifie aussi l'historique, doit être exécuté |
| "Les changements sont dans le stash, l'arbre de travail est propre" | Les changements dans le stash nécessitent aussi le workflow complet |
| "L'utilisateur a seulement dit commit, pas push" | Le push doit suivre immédiatement le commit, aucune instruction supplémentaire nécessaire |
| "Je ferai le push plus tard" | Le push est une étape obligatoire après le commit, ne doit pas être retardé |

---

## Points de contrôle obligatoires

**Avant d'exécuter git push**, confirmer que la boucle qualité a été entièrement complétée :

| Étape | Indicateur de complétion |
|-------|------------------------|
| A. code-simplifier | Le Task agent a été exécuté, les fichiers ont été organisés |
| B. git add + commit/amend | Tous les changements (y compris les modifications du simplifier) ont été commités |
| C. requesting-code-review | La revue n'a trouvé aucun problème, ou tous les problèmes ont été corrigés dans l'itération suivante |

La complétion de la boucle doit être confirmée avant les appels d'outils suivants :

- `Bash` exécutant `git push`
- `Skill` appelant `commit-commands:*`
- `Skill` appelant `pr-review-toolkit:*` (création de PR)

**Après le push**, si une PR existe, exécuter également :
- `Skill` appelant `code-review:code-review --comment`

**Cette règle s'applique à tous les projets, sans aucune exception.**
