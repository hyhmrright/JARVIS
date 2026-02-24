[中文](../../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

Diese Datei bietet Anleitungen für Claude Code bei der Arbeit in dieser Codebasis.

## Branch-Strategie

- **main**: Ausschließlich für Releases. Direkte Commits oder Entwicklung sind nicht erlaubt. Es werden nur Merges aus dev oder anderen Entwicklungsbranches akzeptiert.
- **dev**: Haupt-Entwicklungsbranch. Alle tägliche Entwicklung, Bugfixes und Feature-Entwicklung finden auf diesem Branch oder seinen Unterbranches statt.
- Nach Abschluss der Entwicklung: dev → merge → main → push. Kein Schritt darf übersprungen werden.

## Projektübersicht

JARVIS ist eine AI-Assistenten-Plattform mit RAG-Wissensbasis, Multi-LLM-Unterstützung und Streaming-Konversationen, die eine Monorepo-Struktur verwendet.

## Kernarchitektur

```
JARVIS/
├── backend/           # FastAPI-Backend (Python 3.13 + uv)
│   ├── app/
│   │   ├── main.py    # FastAPI-Einstiegspunkt, Lifespan verwaltet Infra-Verbindungen
│   │   ├── agent/     # LangGraph ReAct-Agent (graph/llm/state)
│   │   ├── api/       # HTTP-Routen (auth/chat/conversations/documents/settings)
│   │   ├── core/      # Konfiguration (Pydantic Settings), Sicherheit (JWT/bcrypt/Fernet), Rate-Limiting
│   │   ├── db/        # SQLAlchemy async Modelle und Sessions
│   │   ├── infra/     # Infrastruktur-Client-Singletons (Qdrant/MinIO/Redis)
│   │   ├── rag/       # RAG-Pipeline (chunker/embedder/indexer)
│   │   └── tools/     # LangGraph-Tools (search/code_exec/file/datetime)
│   ├── alembic/       # Datenbankmigrationen
│   └── tests/         # pytest-Testsuite
├── frontend/          # Vue 3 + TypeScript + Vite + Pinia
│   └── src/
│       ├── api/       # Axios-Singleton + Auth-Interceptor
│       ├── stores/    # Pinia-Stores (auth + chat)
│       ├── pages/     # Seitenkomponenten (Login/Register/Chat/Documents/Settings)
│       ├── locales/   # i18n (zh/en/ja/ko/fr/de)
│       └── router/    # Vue Router + Auth-Guard
├── database/          # Docker-Initialisierungsskripte (postgres/redis/qdrant)
├── docker-compose.yml # Full-Stack-Orchestrierung
└── pyproject.toml     # Root-Dev-Tools-Konfiguration (ruff/pyright/pre-commit), keine Runtime-Deps
```

### Backend-Architektur-Highlights

**LLM-Agent**: `agent/graph.py` implementiert eine ReAct-Schleife mit LangGraph `StateGraph` (llm → tools → llm → END). Pro Anfrage wird eine neue Graph-Instanz erstellt, ohne Checkpoint-Persistierung. Die LLM-Factory (`agent/llm.py`) verteilt über `match/case` an `ChatDeepSeek` / `ChatOpenAI` / `ChatAnthropic`.

**Streaming-Chat**: `POST /api/chat/stream` in `api/chat.py` gibt eine SSE `StreamingResponse` zurück. Hinweis: Der Streaming-Generator verwendet intern eine separate `AsyncSessionLocal`-Session (die Request-Level-Session kann nicht wiederverwendet werden, da sie sich schließt, wenn der Handler zurückkehrt).

**RAG-Pipeline**: Dokument-Upload → `extract_text()` → `chunk_text()` (Sliding Window, 500 Wörter/50 Wörter Überlappung) → `OpenAIEmbeddings` (text-embedding-3-small, 1536 Dimensionen) → Qdrant Upsert. Eine Collection pro Benutzer (`user_{id}`). Hinweis: RAG-Retrieval ist noch nicht in den Agent-Konversationsfluss integriert.

**Datenbankmodelle**: 5 Tabellen — `users`, `user_settings` (JSONB speichert Fernet-verschlüsselte API-Keys), `conversations`, `messages` (unveränderlich), `documents` (Soft-Delete). Alle verwenden UUID-Primärschlüssel.

**Infrastruktur-Singletons**: Qdrant verwendet modulebene Globale + verzögerte Initialisierung + asyncio.Lock; MinIO verwendet `@lru_cache` + `asyncio.to_thread()` (synchrones SDK); PostgreSQL verwendet modulebene Engine + Sessionmaker.

### Frontend-Architektur-Highlights

**Zustandsverwaltung**: Zwei Pinia-Stores — `auth.ts` (JWT-Token wird in localStorage persistiert) und `chat.ts` (Konversationsliste + SSE-Streaming-Nachrichten). SSE verwendet natives `fetch` + `ReadableStream` statt Axios (Axios unterstützt keine Streaming-Response-Bodies).

**Routing**: 5 Routen, alle Seitenkomponenten werden lazy-loaded. Der `beforeEach`-Guard prüft `auth.isLoggedIn`.

**API-Client**: Axios-Instanz mit `baseURL: "/api"`, Request-Interceptor liest Token aus localStorage. Dev-Server leitet `/api` → `http://backend:8000` weiter.

**Internationalisierung**: vue-i18n, 6 Sprachen, Erkennungspriorität: localStorage → navigator.language → zh.

## Entwicklungsumgebung

- **Python**: 3.13 (`.python-version`)
- **Paketmanager**: Backend `uv`, Frontend `bun`
- **Virtuelle Umgebung**: `.venv` (automatisch von uv verwaltet)

## Häufig verwendete Befehle

### Umgebungseinrichtung
```bash
bash scripts/init-env.sh             # Erstausführung, generiert .env (mit zufälligen Passwörtern/Schlüsseln)
uv sync                              # Python-Abhängigkeiten installieren
cd frontend && bun install            # Frontend-Abhängigkeiten installieren
pre-commit install                    # Git Hooks installieren
```

### Anwendung ausführen
```bash
# Nur Infrastruktur-Services starten (für lokale Entwicklung)
docker compose up -d postgres redis qdrant minio

# Backend (im backend/-Verzeichnis)
uv run alembic upgrade head           # Datenbankmigration
uv run uvicorn app.main:app --reload  # Dev-Server :8000

# Frontend (im frontend/-Verzeichnis)
bun run dev                           # Dev-Server :5173 (Proxy /api → backend:8000)

# Full-Stack Docker
docker compose up -d                  # Frontend :3000 · Backend :8000
```

### Code-Qualität
```bash
# Backend
ruff check                   # Lint
ruff check --fix             # Lint + Auto-Fix
ruff format                  # Formatierung
pyright                      # Typprüfung

# Frontend (im frontend/-Verzeichnis)
bun run lint                 # ESLint
bun run lint:fix             # ESLint + Auto-Fix
bun run format               # Prettier
bun run type-check           # vue-tsc
```

### Tests
```bash
# Im backend/-Verzeichnis ausführen
uv run pytest tests/ -v                        # Alle Tests
uv run pytest tests/api/test_auth.py -v        # Einzelne Datei
uv run pytest tests/api/test_auth.py::test_login -v  # Einzelner Testfall
```

### Pre-commit Hooks
```bash
pre-commit run --all-files   # Alle Hooks manuell ausführen
```

Hooks umfassen: YAML/TOML/JSON-Formatprüfung, uv.lock-Synchronisierung, Ruff Lint+Format, ESLint, Pyright, vue-tsc-Typprüfung, Gitleaks-Secret-Scanning, Blockierung direkter Commits auf main.

### Abhängigkeitsverwaltung
```bash
# Python (Root-pyproject.toml verwaltet Dev-Tools, backend/pyproject.toml verwaltet Runtime-Deps)
uv add <Paketname>           # Abhängigkeit hinzufügen (im entsprechenden Verzeichnis ausführen)
uv add --group dev <Paketname> # Entwicklungsabhängigkeit hinzufügen
uv lock                      # Lock nach manueller Bearbeitung von pyproject.toml neu generieren

# Frontend
cd frontend && bun add <Paketname>
```

## Tool-Konfiguration

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **ESLint**: Flat Config, typescript-eslint + eslint-plugin-vue + prettier
- **TypeScript**: strict, Bundler-Resolution, `@/*` → `src/*`

## Umgebungsvariablen

Alle sensiblen Konfigurationen (Datenbankpasswort, JWT-Secret, Verschlüsselungsschlüssel, MinIO-Anmeldedaten) haben keine Standardwerte und müssen über `.env` oder Umgebungsvariablen bereitgestellt werden. Führen Sie `bash scripts/init-env.sh` zur automatischen Generierung aus. Nur `DEEPSEEK_API_KEY` erfordert manuelle Eingabe.

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
