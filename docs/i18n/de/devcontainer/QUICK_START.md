[English](../../../../.devcontainer/QUICK_START.md) | [中文](../../zh/devcontainer/QUICK_START.md) | [日本語](../../ja/devcontainer/QUICK_START.md) | [한국어](../../ko/devcontainer/QUICK_START.md) | [Français](../../fr/devcontainer/QUICK_START.md) | [Deutsch](QUICK_START.md)

# 🚀 Dev Container Kurzreferenz

## Ein-Klick-Start (VS Code)

```bash
# 1. VS Code öffnen
code path/to/JARVIS

# 2. F1 drücken, eingeben:
Dev Containers: Reopen in Container

# 3. Auf den Build warten, mit dem Programmieren beginnen!
```

---

## Kommandozeilen-Verwendung

### Image bauen
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### Programm ausführen
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### Interaktive Shell starten
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## Häufig verwendete Befehle

### Im Container
```bash
# Abhängigkeiten installieren
uv sync

# Programm ausführen
uv run python main.py

# Code-Prüfung
uv run ruff check main.py
uv run ruff format main.py
uv run mypy app

# Git-Operationen
git status
pre-commit run --all-files
```

---

## Dateistruktur

```
.devcontainer/
├── devcontainer.json        # VS Code Konfiguration
├── Dockerfile               # Image-Definition
├── README.md                # Benutzerhandbuch (Chinesisch)
├── QUICK_START.md           # Kurzreferenz (Chinesisch)
└── docs/i18n/
    ├── readme/              # Benutzerhandbuch-Übersetzungen
    │   └── README.{en,ja,ko,fr,de}.md
    └── quick-start/         # Kurzreferenz-Übersetzungen
        └── QUICK_START.{en,ja,ko,fr,de}.md
```

---

## Schnelltest

```bash
# Python testen
docker run --rm jarvis-dev python --version

# uv testen
docker run --rm jarvis-dev uv --version

# Bun testen
docker run --rm jarvis-dev bun --version
```

---

## Fehlerbehebung

| Problem | Lösung |
|---------|---------|
| Docker läuft nicht | Docker Desktop starten |
| Build fehlgeschlagen | `docker system prune -a` um den Cache zu leeren |
| VS Code kann nicht verbinden | VS Code neu starten oder Container neu bauen |
| Abhängigkeit nicht gefunden | `uv run python` statt `python` verwenden |

---

## Umgebungsinformationen

- **Python**: 3.13
- **uv**: latest
- **Bun**: latest
- **Git**: latest
- **Basis-Image**: python:3.13-slim
- **Benutzer**: vscode (nicht-root)
- **Arbeitsverzeichnis**: /workspace

---

## Verwandte Dokumentation

- [Vollständiges Benutzerhandbuch (Deutsch)](README.md)

---

**Tipp**: Der erste Build dauert etwa 3-5 Minuten, nachfolgende Starts nur 10-20 Sekunden!
