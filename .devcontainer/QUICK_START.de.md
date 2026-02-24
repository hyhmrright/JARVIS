[中文](QUICK_START.md) | [English](QUICK_START.en.md) | [日本語](QUICK_START.ja.md) | [한국어](QUICK_START.ko.md) | [Français](QUICK_START.fr.md) | [Deutsch](QUICK_START.de.md)

# 🚀 Dev Container Kurzreferenz

## Ein-Klick-Start (VS Code)

```bash
# 1. VS Code öffnen
code /Users/hyh/code/JARVIS

# 2. F1 drücken, eingeben:
Dev Containers: Reopen in Container

# 3. Auf den Build warten, mit dem Programmieren beginnen!
```

---

## Kommandozeilen-Verwendung

### Image bauen
```bash
cd /Users/hyh/code/JARVIS
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
uv run pyright main.py

# Git-Operationen
git status
pre-commit run --all-files
```

---

## Dateistruktur

```
.devcontainer/
├── devcontainer.json     # VS Code Konfiguration
├── Dockerfile            # Image-Definition
├── README.md             # Benutzerhandbuch
├── CHANGELOG.md          # Konfigurationsprotokoll
├── SETUP_COMPLETE.md     # Vollständiger Bericht
├── TEST_REPORT.md        # Testergebnisse
└── test.sh               # Verifizierungsskript
```

---

## Schnelltest

```bash
# Konfiguration überprüfen
./.devcontainer/test.sh

# Python testen
docker run --rm jarvis-dev python --version

# uv testen
docker run --rm jarvis-dev uv --version

# Vollständigen Workflow testen
docker run --rm -v $(pwd):/workspace jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
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

- **Python**: 3.13.11
- **uv**: 0.9.26
- **Git**: 2.47.3
- **Basis-Image**: python:3.13-slim
- **Benutzer**: vscode (nicht-root)
- **Arbeitsverzeichnis**: /workspace

---

## Verwandte Dokumentation

- [Vollständiges Benutzerhandbuch](.devcontainer/README.md)
- [Konfigurationshinweise](.devcontainer/CHANGELOG.md)
- [Testbericht](.devcontainer/TEST_REPORT.md)
- [Vollständiger Einrichtungsbericht](.devcontainer/SETUP_COMPLETE.md)

---

**Tipp**: Der erste Build dauert etwa 3-5 Minuten, nachfolgende Starts nur 10-20 Sekunden!
