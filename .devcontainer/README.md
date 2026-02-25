[中文](../docs/i18n/zh/devcontainer/README.md) | [日本語](../docs/i18n/ja/devcontainer/README.md) | [한국어](../docs/i18n/ko/devcontainer/README.md) | [Français](../docs/i18n/fr/devcontainer/README.md) | [Deutsch](../docs/i18n/de/devcontainer/README.md)

# Dev Container User Guide

## What is a Dev Container?

A Dev Container is a standardized development environment configuration that uses Docker containers to provide a consistent development experience. You get the same development environment regardless of what machine you are on.

## Features

✅ **Pre-configured Python 3.13 environment**
✅ **Automatic uv package manager installation**
✅ **Pre-installed Bun runtime** (frontend development)
✅ **Pre-installed development tools** (Ruff, Pyright, Pre-commit)
✅ **Automatic VS Code extension installation**
✅ **Automatic `uv sync`, `pre-commit install` and `bun install` execution**
✅ **Code formatting and Linting pre-configured**

## How to Use

### Method 1: VS Code (Recommended)

1. **Install required software**:
   - Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Install [VS Code](https://code.visualstudio.com/)
   - Install VS Code extension: `Dev Containers` (ms-vscode-remote.remote-containers)

2. **Open the project**:
   - Open this project folder in VS Code
   - VS Code will detect the `.devcontainer` configuration
   - Click the "Reopen in Container" button that appears in the bottom right
   - Or press `F1` → type "Dev Containers: Reopen in Container"

3. **Wait for the build**:
   - The first time you open it, the Docker image will be built (about 2-5 minutes)
   - Subsequent opens will be fast (10-20 seconds)

4. **Start developing**:
   - All dependencies are automatically installed
   - Code quality tools are pre-configured
   - You can directly run `python main.py`

### Method 2: Command Line

```bash
# Build the container
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# Run the container
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# Inside the container
uv sync
python main.py
```
