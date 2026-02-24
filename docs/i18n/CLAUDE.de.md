[中文](../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

Diese Datei bietet Anleitungen für Claude Code bei der Arbeit in dieser Codebasis.

## Branch-Strategie

- **main**: Ausschließlich für Releases. Direkte Commits oder Entwicklung sind nicht erlaubt. Es werden nur Merges aus dev oder anderen Entwicklungsbranches akzeptiert.
- **dev**: Haupt-Entwicklungsbranch. Alle tägliche Entwicklung, Bugfixes und Feature-Entwicklung finden auf diesem Branch oder seinen Unterbranches statt.
- Nach Abschluss der Entwicklung: dev → merge → main → push. Kein Schritt darf übersprungen werden.

## Projektübersicht

JARVIS ist eine AI-Assistenten-Plattform mit RAG-Wissensbasis, Multi-LLM-Unterstützung und Streaming-Konversationen, die eine Monorepo-Struktur verwendet.

## Kernarchitektur

- **backend/**: FastAPI + LangGraph + SQLAlchemy (PostgreSQL) + Qdrant (Vektorspeicher) + MinIO (Dateispeicher) + Redis
- **frontend/**: Vue 3 + TypeScript + Vite + Pinia
- **Root pyproject.toml**: Verwaltet nur Entwicklungstools (ruff, pyright, pre-commit), keine Laufzeitabhängigkeiten
- **LLM**: Unterstützt DeepSeek / OpenAI / Anthropic, angetrieben durch LangGraph StateGraph

## Entwicklungsumgebung

- **Python-Version**: 3.13 (`.python-version`)
- **Paketmanager**: `uv`
- **Virtuelle Umgebung**: `.venv` (automatisch verwaltet)

## Häufig verwendete Befehle

### Umgebungseinrichtung
```bash
uv sync                      # Alle Abhängigkeiten installieren
```

### Anwendung ausführen
```bash
# Backend (im backend/-Verzeichnis)
uv run uvicorn app.main:app --reload

# Frontend (im frontend/-Verzeichnis)
bun run dev

# Full Stack (Root-Verzeichnis)
docker-compose up -d
```

### Code-Qualitätsprüfungen
```bash
ruff check                   # Code-Linting
ruff check --fix             # Probleme automatisch beheben
ruff format                  # Code-Formatierung
pyright                      # Typprüfung
```

### Tests
```bash
# Im backend/-Verzeichnis ausführen
uv run pytest tests/ -v                        # Alle Tests ausführen
uv run pytest tests/api/test_auth.py -v        # Eine bestimmte Testdatei ausführen
```

### Pre-commit Hooks
```bash
pre-commit install           # Git Hooks installieren
pre-commit run --all-files   # Alle Hooks manuell ausführen
```

Pre-commit führt automatisch aus:
- YAML/TOML/JSON-Formatprüfung
- uv.lock-Synchronisierungsprüfung
- Ruff Lint und Format
- Prüfung auf abschließende Leerzeilen und nachfolgende Leerzeichen

### Abhängigkeitsverwaltung
```bash
uv add <Paketname>           # Produktionsabhängigkeit hinzufügen
uv add --group dev <Paketname> # Entwicklungsabhängigkeit hinzufügen
uv sync --upgrade            # Abhängigkeiten aktualisieren
uv lock                      # uv.lock nach manueller Bearbeitung von pyproject.toml neu generieren
```

## Tool-Konfiguration

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **Pre-commit**: Führt uv-lock, ruff-check, ruff-format und Standard-Dateiprüfungen aus

---

# Globale Entwicklungsregeln

## Selbstprüfung vor Git-Operationen

**Vor jedem `git commit`, `git push` oder Commit/Push-Skill-Aufruf muss eine Selbstprüfung durchgeführt werden:**

```
Wurden in dieser Sitzung Dateien geändert?
   → Ja → Wurde die Qualitätsschleife (simplifier → commit → review) vollständig durchlaufen?
           → Nein → [STOP] Qualitätsschleife sofort ausführen
           → Ja → Git-Operation fortsetzen
   → Nein → Gibt es nicht commitete Änderungen im Arbeitsbaum? (git diff / git diff --cached / git stash list)
             → Ja (einschließlich Stash) → [STOP] Zuerst die vollständige Qualitätsschleife durchführen
             → Nein → Git-Operation fortsetzen
```

---

## Obligatorischer Workflow für Codeänderungen

### Tool-Referenz

| Tool | Typ | Aufrufmethode | Ausführungszeitpunkt |
|------|-----|--------------|----------------------|
| code-simplifier | Task agent | `Task`-Tool, `subagent_type: "code-simplifier:code-simplifier"` | Vor dem Commit |
| Pre-Push Code-Review | Skill | `Skill: superpowers:requesting-code-review` | Nach dem Commit, vor dem Push |
| PR Code-Review | Skill | `Skill: code-review:code-review --comment` | Nach dem Push (erfordert vorhandene PR) |

### Auslösebedingungen (eine reicht aus)

- Eine Datei wurde mit Edit / Write / NotebookEdit geändert
- Der Benutzer beabsichtigt, Änderungen in Git zu persistieren oder zum Remote zu pushen (einschließlich Ausdrücke wie "synchronisieren", "hochladen", "PR erstellen", "archivieren", "ship" usw.)
- Ein Commit/Push-bezogener Skill soll aufgerufen werden

### Ausführungsschritte (feste Reihenfolge, nicht überspringbar)

```
Code schreiben / Dateien ändern
      ↓
╔══════════════════ Qualitätsschleife (wiederholen bis keine Probleme) ══════════════════╗
║                                                                                         ║
║  A. [PFLICHT] Task: code-simplifier                                                     ║
║     (Task agent, ändert Dateien direkt)                                                ║
║          ↓                                                                              ║
║  B. git add + commit                                                                    ║
║     Erster Eintritt → git commit                                                        ║
║     Wiedereintritt nach Fix → git commit --amend (Historie vor Push sauber halten)       ║
║          ↓                                                                              ║
║  C. [PFLICHT] Skill: superpowers:requesting-code-review                                 ║
║     (BASE_SHA=HEAD~1, HEAD_SHA=HEAD bereitstellen)                                      ║
║          ↓                                                                              ║
║     Probleme gefunden?                                                                  ║
║       Ja → Code beheben ──────────────────────────→ Zurück zu Schritt A                ║
║       Nein ↓                                                                            ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
      ↓
git push (sofort ausführen, nicht verzögern)
      ↓ (wenn eine GitHub PR existiert)
[PFLICHT] Skill: code-review:code-review --comment
```

**Wichtige Hinweise:**
- Die Qualitätsschleife muss vollständig ausgeführt werden (A→B→C) und C darf keine Probleme aufweisen, bevor sie verlassen wird
- Bei Wiedereintritt in die Schleife nach Korrekturen `--amend` verwenden (einen einzelnen Commit vor dem Push beibehalten)
- `--amend` ist kein Grund, das Review zu überspringen; C muss trotzdem erneut ausgeführt werden

---

## Häufige Ausreden zum Überspringen des Workflows (alle verboten)

Die folgenden Gründe dürfen **nicht** zum Überspringen des Workflows verwendet werden:

| Ausrede | Korrekte Vorgehensweise |
|---------|------------------------|
| "Es ist nur eine einfache einzeilige Änderung" | Muss unabhängig von der Änderungsgröße ausgeführt werden |
| "Der Benutzer hat nur Commit gesagt, nicht Review" | Der Commit selbst ist eine Auslösebedingung |
| "Ich habe gerade ähnlichen Code reviewed" | Muss nach jeder Änderung erneut ausgeführt werden |
| "Das ist eine Testdatei / Dokumentation, keine Kernlogik" | Gilt, solange Edit/Write zum Ändern von Dateien verwendet wurde |
| "Man muss vor dem Review pushen" | Review muss vor dem Push erfolgen |
| "Der Benutzer drängt, erst mal committen" | Der Workflow wird nicht wegen Zeitdruck übersprungen |
| "Ich kenne diesen Code sehr gut" | Vertrautheit beeinflusst die Workflow-Anforderungen nicht |
| "Diese Änderungen wurden nicht in dieser Sitzung gemacht" | Muss ausgeführt werden, solange nicht commitete Änderungen vorhanden sind |
| "Der Benutzer hat das Wort 'Commit' nicht verwendet" | Wird ausgelöst, sobald die Absicht zum Committen/Pushen besteht |
| "Das ist ein --amend, kein neuer Commit" | --amend ändert ebenfalls die Historie, muss ausgeführt werden |
| "Änderungen sind im Stash, der Arbeitsbaum ist sauber" | Änderungen im Stash erfordern ebenfalls den vollständigen Workflow |
| "Der Benutzer hat nur Commit gesagt, nicht Push" | Push muss sofort nach dem Commit folgen, keine zusätzliche Anweisung nötig |
| "Ich pushe später" | Push ist ein obligatorischer Folgeschritt nach dem Commit, darf nicht verzögert werden |

---

## Obligatorische Checkpoints

**Vor der Ausführung von git push** muss bestätigt werden, dass die Qualitätsschleife vollständig durchlaufen wurde:

| Schritt | Abschlussindikator |
|---------|-------------------|
| A. code-simplifier | Task agent wurde ausgeführt, Dateien wurden organisiert |
| B. git add + commit/amend | Alle Änderungen (einschließlich Simplifier-Modifikationen) wurden committet |
| C. requesting-code-review | Review hat keine Probleme gefunden, oder alle Probleme wurden in der nächsten Iteration behoben |

Der Abschluss der Schleife muss vor den folgenden Tool-Aufrufen bestätigt werden:

- `Bash` führt `git push` aus
- `Skill` ruft `commit-commands:*` auf
- `Skill` ruft `pr-review-toolkit:*` auf (PR-Erstellung)

**Nach dem Push**, wenn eine PR existiert, auch ausführen:
- `Skill` ruft `code-review:code-review --comment` auf

**Diese Regel gilt für alle Projekte, ohne Ausnahme.**
