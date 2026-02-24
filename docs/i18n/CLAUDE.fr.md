[中文](../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

Ce fichier fournit des directives pour Claude Code lorsqu'il travaille dans cette base de code.

## Stratégie de branches

- **main** : Utilisé uniquement pour les releases. Les commits directs ou le développement sont interdits. Seuls les merges depuis dev ou d'autres branches de développement sont acceptés.
- **dev** : Branche de développement principale. Tout le développement quotidien, les corrections de bugs et le développement de fonctionnalités se font sur cette branche ou ses sous-branches.
- Après le développement : dev → merge → main → push. Aucune étape ne peut être ignorée.

## Aperçu du projet

JARVIS est une plateforme d'assistant IA dotée d'une base de connaissances RAG, d'un support multi-LLM et de conversations en streaming, utilisant une structure monorepo.

## Architecture principale

- **backend/** : FastAPI + LangGraph + SQLAlchemy (PostgreSQL) + Qdrant (base vectorielle) + MinIO (stockage de fichiers) + Redis
- **frontend/** : Vue 3 + TypeScript + Vite + Pinia
- **pyproject.toml racine** : Gère uniquement les outils de développement (ruff, pyright, pre-commit), pas de dépendances d'exécution
- **LLM** : Supporte DeepSeek / OpenAI / Anthropic, piloté par LangGraph StateGraph

## Environnement de développement

- **Version Python** : 3.13 (`.python-version`)
- **Gestionnaire de paquets** : `uv`
- **Environnement virtuel** : `.venv` (géré automatiquement)

## Commandes courantes

### Configuration de l'environnement
```bash
uv sync                      # Installer toutes les dépendances
```

### Lancement de l'application
```bash
# Backend (dans le répertoire backend/)
uv run uvicorn app.main:app --reload

# Frontend (dans le répertoire frontend/)
bun run dev

# Stack complète (répertoire racine)
docker-compose up -d
```

### Vérification de la qualité du code
```bash
ruff check                   # Lint du code
ruff check --fix             # Correction automatique des problèmes
ruff format                  # Formatage du code
pyright                      # Vérification des types
```

### Tests
```bash
# Exécuter dans le répertoire backend/
uv run pytest tests/ -v                        # Exécuter tous les tests
uv run pytest tests/api/test_auth.py -v        # Exécuter un fichier de test spécifique
```

### Pre-commit Hooks
```bash
pre-commit install           # Installer les git hooks
pre-commit run --all-files   # Exécuter manuellement tous les hooks
```

Pre-commit exécute automatiquement :
- Vérification du format YAML/TOML/JSON
- Vérification de la synchronisation uv.lock
- Ruff lint et format
- Vérification des lignes vides en fin de fichier et des espaces en fin de ligne

### Gestion des dépendances
```bash
uv add <paquet>              # Ajouter une dépendance de production
uv add --group dev <paquet>  # Ajouter une dépendance de développement
uv sync --upgrade            # Mettre à jour les dépendances
uv lock                      # Régénérer uv.lock après modification manuelle de pyproject.toml
```

## Configuration des outils

- **Ruff** : line-length=88, target-version="py313", quote-style="double"
- **Pyright** : typeCheckingMode="basic"
- **Pre-commit** : Exécute uv-lock, ruff-check, ruff-format et les vérifications de fichiers standard

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
