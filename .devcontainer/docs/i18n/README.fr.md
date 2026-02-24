[中文](../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# Guide d'utilisation Dev Container

## Qu'est-ce qu'un Dev Container ?

Un Dev Container est une configuration d'environnement de développement standardisée qui utilise des conteneurs Docker pour fournir une expérience de développement cohérente. Vous obtenez le même environnement de développement quelle que soit la machine utilisée.

## Fonctionnalités

✅ **Environnement Python 3.13 préconfigurée**
✅ **Installation automatique du gestionnaire de paquets uv**
✅ **Runtime Bun préinstallé** (développement frontend)
✅ **Outils de développement préinstallés** (Ruff, Pyright, Pre-commit)
✅ **Installation automatique des extensions VS Code**
✅ **Exécution automatique de `uv sync`, `pre-commit install` et `bun install`**
✅ **Formatage du code et Linting préconfigurés**

## Comment utiliser

### Méthode 1 : VS Code (Recommandée)

1. **Installer les logiciels requis** :
   - Installer [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Installer [VS Code](https://code.visualstudio.com/)
   - Installer l'extension VS Code : `Dev Containers` (ms-vscode-remote.remote-containers)

2. **Ouvrir le projet** :
   - Ouvrir ce dossier de projet dans VS Code
   - VS Code détectera la configuration `.devcontainer`
   - Cliquer sur le bouton "Reopen in Container" qui apparaît en bas à droite
   - Ou appuyer sur `F1` → taper "Dev Containers: Reopen in Container"

3. **Attendre la construction** :
   - La première ouverture construira l'image Docker (environ 2-5 minutes)
   - Les ouvertures suivantes seront rapides (10-20 secondes)

4. **Commencer à développer** :
   - Toutes les dépendances sont automatiquement installées
   - Les outils de qualité de code sont préconfigurés
   - Vous pouvez directement exécuter `python main.py`

### Méthode 2 : Ligne de commande

```bash
# Construire le conteneur
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# Exécuter le conteneur
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# Dans le conteneur
uv sync
python main.py
```
