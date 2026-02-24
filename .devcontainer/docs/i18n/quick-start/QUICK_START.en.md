[中文](../../../QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container Quick Reference

## One-Click Start (VS Code)

```bash
# 1. Open VS Code
code path/to/JARVIS

# 2. Press F1, type:
Dev Containers: Reopen in Container

# 3. Wait for the build to finish, start coding!
```

---

## Command Line Usage

### Build Image
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### Run Program
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### Enter Interactive Shell
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## Common Commands

### Inside the Container
```bash
# Install dependencies
uv sync

# Run program
uv run python main.py

# Code checking
uv run ruff check main.py
uv run ruff format main.py
uv run pyright main.py

# Git operations
git status
pre-commit run --all-files
```

---

## File Structure

```
.devcontainer/
├── devcontainer.json        # VS Code configuration
├── Dockerfile               # Image definition
├── README.md                # User guide (Chinese)
├── QUICK_START.md           # Quick reference (Chinese)
└── docs/i18n/
    ├── readme/              # User guide translations
    │   └── README.{en,ja,ko,fr,de}.md
    └── quick-start/         # Quick reference translations
        └── QUICK_START.{en,ja,ko,fr,de}.md
```

---

## Quick Test

```bash
# Test Python
docker run --rm jarvis-dev python --version

# Test uv
docker run --rm jarvis-dev uv --version

# Test Bun
docker run --rm jarvis-dev bun --version
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker not running | Start Docker Desktop |
| Build failed | `docker system prune -a` to clear cache |
| VS Code cannot connect | Restart VS Code or rebuild container |
| Dependency not found | Use `uv run python` instead of `python` |

---

## Environment Info

- **Python**: 3.13
- **uv**: latest
- **Bun**: latest
- **Git**: latest
- **Base image**: python:3.13-slim
- **User**: vscode (non-root)
- **Working directory**: /workspace

---

## Related Documentation

- [Full User Guide (English)](../readme/README.en.md)
- [Full User Guide (中文)](../../../README.md)

---

**Tip**: The first build takes about 3-5 minutes, subsequent starts only take 10-20 seconds!
