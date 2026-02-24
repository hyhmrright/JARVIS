[中文](../../../README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

# Dev Container Benutzerhandbuch

## Was ist ein Dev Container?

Ein Dev Container ist eine standardisierte Entwicklungsumgebungskonfiguration, die Docker-Container verwendet, um ein konsistentes Entwicklungserlebnis zu bieten. Unabhängig von der verwendeten Maschine erhalten Sie die gleiche Entwicklungsumgebung.

## Funktionen

✅ **Vorkonfigurierte Python 3.13 Umgebung**
✅ **Automatische Installation des uv Paketmanagers**
✅ **Vorinstallierte Bun-Runtime** (Frontend-Entwicklung)
✅ **Vorinstallierte Entwicklungswerkzeuge** (Ruff, Pyright, Pre-commit)
✅ **Automatische Installation von VS Code Erweiterungen**
✅ **Automatische Ausführung von `uv sync`, `pre-commit install` und `bun install`**
✅ **Codeformatierung und Linting vorkonfiguriert**

## Verwendung

### Methode 1: VS Code (Empfohlen)

1. **Erforderliche Software installieren**:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop) installieren
   - [VS Code](https://code.visualstudio.com/) installieren
   - VS Code Erweiterung installieren: `Dev Containers` (ms-vscode-remote.remote-containers)

2. **Projekt öffnen**:
   - Diesen Projektordner in VS Code öffnen
   - VS Code erkennt die `.devcontainer` Konfiguration
   - Auf die Schaltfläche "Reopen in Container" klicken, die unten rechts erscheint
   - Oder `F1` drücken → "Dev Containers: Reopen in Container" eingeben

3. **Auf den Build warten**:
   - Beim ersten Öffnen wird das Docker-Image gebaut (ca. 2-5 Minuten)
   - Nachfolgende Öffnungen sind schnell (10-20 Sekunden)

4. **Mit der Entwicklung beginnen**:
   - Alle Abhängigkeiten sind automatisch installiert
   - Codequalitätswerkzeuge sind vorkonfiguriert
   - Sie können direkt `python main.py` ausführen

### Methode 2: Kommandozeile

```bash
# Container bauen
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# Container ausführen
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# Im Container
uv sync
python main.py
```
