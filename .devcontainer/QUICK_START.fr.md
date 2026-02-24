[中文](QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container Reference Rapide

## Démarrage en un clic (VS Code)

```bash
# 1. Ouvrir VS Code
code path/to/JARVIS

# 2. Appuyer sur F1, taper :
Dev Containers: Reopen in Container

# 3. Attendre la fin de la construction, commencer à coder !
```

---

## Utilisation en ligne de commande

### Construire l'image
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### Exécuter le programme
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### Entrer dans le shell interactif
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## Commandes courantes

### Dans le conteneur
```bash
# Installer les dépendances
uv sync

# Exécuter le programme
uv run python main.py

# Vérification du code
uv run ruff check main.py
uv run ruff format main.py
uv run pyright main.py

# Opérations Git
git status
pre-commit run --all-files
```

---

## Structure des fichiers

```
.devcontainer/
├── devcontainer.json     # Configuration VS Code
├── Dockerfile            # Définition de l'image
├── README[.lang].md      # Guide d'utilisation (multilingue)
└── QUICK_START[.lang].md # Référence rapide (multilingue)
```

---

## Test rapide

```bash
# Tester Python
docker run --rm jarvis-dev python --version

# Tester uv
docker run --rm jarvis-dev uv --version

# Tester Bun
docker run --rm jarvis-dev bun --version
```

---

## Dépannage

| Problème | Solution |
|----------|----------|
| Docker ne fonctionne pas | Démarrer Docker Desktop |
| Échec de la construction | `docker system prune -a` pour vider le cache |
| VS Code ne peut pas se connecter | Redémarrer VS Code ou reconstruire le conteneur |
| Dépendance introuvable | Utiliser `uv run python` au lieu de `python` |

---

## Informations sur l'environnement

- **Python** : 3.13
- **uv** : latest
- **Bun** : latest
- **Git** : latest
- **Image de base** : python:3.13-slim
- **Utilisateur** : vscode (non-root)
- **Répertoire de travail** : /workspace

---

## Documentation associée

- [Guide d'utilisation complet](README.fr.md)

---

**Astuce** : La première construction prend environ 3-5 minutes, les démarrages suivants ne prennent que 10-20 secondes !
