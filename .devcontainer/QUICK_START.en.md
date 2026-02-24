[中文](QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container Quick Reference

## One-Click Start (VS Code)

```bash
# 1. Open VS Code
code /Users/hyh/code/JARVIS

# 2. Press F1, type:
Dev Containers: Reopen in Container

# 3. Wait for the build to finish, start coding!
```

---

## Command Line Usage

### Build Image
```bash
cd /Users/hyh/code/JARVIS
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
├── devcontainer.json     # VS Code configuration
├── Dockerfile            # Image definition
├── README.md             # User guide
├── CHANGELOG.md          # Configuration log
├── SETUP_COMPLETE.md     # Complete report
├── TEST_REPORT.md        # Test results
└── test.sh               # Verification script
```

---

## Quick Test

```bash
# Verify configuration
./.devcontainer/test.sh

# Test Python
docker run --rm jarvis-dev python --version

# Test uv
docker run --rm jarvis-dev uv --version

# Test full workflow
docker run --rm -v $(pwd):/workspace jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
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

- **Python**: 3.13.11
- **uv**: 0.9.26
- **Git**: 2.47.3
- **Base image**: python:3.13-slim
- **User**: vscode (non-root)
- **Working directory**: /workspace

---

## Related Documentation

- [Full User Guide](.devcontainer/README.md)
- [Configuration Notes](.devcontainer/CHANGELOG.md)
- [Test Report](.devcontainer/TEST_REPORT.md)
- [Complete Setup Report](.devcontainer/SETUP_COMPLETE.md)

---

**Tip**: The first build takes about 3-5 minutes, subsequent starts only take 10-20 seconds!
