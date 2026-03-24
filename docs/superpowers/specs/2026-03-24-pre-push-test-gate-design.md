# Pre-Push Test Gate Design

**Date:** 2026-03-24
**Status:** Approved
**Problem:** pytest is absent from all local check layers. Any test failure is only caught by GitHub CI after push, causing repeated CI red builds.

## Root Cause

| Check | pre-commit | CLAUDE.md loop | GitHub CI |
|-------|-----------|----------------|-----------|
| ruff lint/format | ✅ | ✅ | ✅ |
| mypy | ✅ | ✅ | ✅ |
| eslint | ✅ | ✅ | ✅ |
| vue-tsc | ✅ | ✅ | ✅ |
| **pytest** | ❌ | ❌ | ✅ |
| **pytest --collect-only** | ❌ | ❌ | ✅ |

pytest is never run locally, so runtime test failures only surface on CI.

## Solution: Dual-Layer Test Gate (Plan C)

Three changes working together.

---

## Layer 1 — pre-commit stage: `pytest --collect-only -q`

Runs on every `git commit` when any `.py` file under `backend/` is staged.

- Catches: import errors, missing modules, FastAPI response_model registration errors, broken fixtures — without executing any test
- Requires: `POSTGRES_PASSWORD` env var must be set (conftest.py reads it at module import time via `os.environ["POSTGRES_PASSWORD"]`). Engine objects are only created inside fixtures, so **no live DB connection is needed**.
- Speed: ~2 seconds

**Environment prerequisite:** `POSTGRES_PASSWORD` must be available in the shell. The hook entry uses `scripts/run-tests.sh` which auto-loads `.env` from the repo root.

**Hook definition:**
```yaml
- id: pytest-collect
  name: pytest import check (no DB required)
  language: system
  entry: bash scripts/run-tests.sh collect
  stages: [pre-commit]
  pass_filenames: false
  files: ^backend/.*\.py$
```

---

## Layer 2 — pre-push stage: `pytest tests/ -x -q --tb=short`

Runs on every `git push` when any `.py` file under `backend/` was changed in the push.

- Catches: all runtime test failures, logic bugs, ordering bugs, DB-dependent tests
- Requires: `POSTGRES_PASSWORD` + `DATABASE_URL`; postgres + redis Docker services running; `jarvis_test` DB migrated
- Fail-fast (`-x`) for immediate feedback
- **Known gap:** pushes that only change non-Python files (docs, YAML, frontend) will not trigger this hook. Those changes rarely affect backend tests.

**Note on `default_stages`:** The existing `.pre-commit-config.yaml` has `default_stages: [pre-commit]`. The `stages: [pre-push]` field on this hook is mandatory — it overrides the default and must not be omitted.

**Hook definition:**
```yaml
- id: pytest-full
  name: pytest full suite (requires postgres + redis)
  language: system
  entry: bash scripts/run-tests.sh full
  stages: [pre-push]
  pass_filenames: false
  files: ^backend/.*\.py$
```

---

## Layer 3 — CLAUDE.md quality loop update

Add pytest as an explicit mandatory step after `ruff + mypy`, before the Quality Loop:

```
[REQUIRED] Run backend tests:
  cd backend && uv run pytest tests/ -x -q --tb=short
  (If DB unavailable: uv run pytest --collect-only -q at minimum)
  Any test failure → fix before entering quality loop. No exceptions.
```

Add to the "Common Excuses" table:

| "Tests pass on CI, no need to run locally" | Must run pytest before every push |
| "DB is not running, can't run tests" | `docker compose up -d postgres redis` then run pytest |

---

## Files to Change

### 1. `scripts/run-tests.sh` (new file)

Loads `.env` and runs pytest. Used by both pre-commit hooks and manually.
Uses `git rev-parse --show-toplevel` to locate the repo root unambiguously regardless of invocation directory.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Find repo root unambiguously (works regardless of CWD or how script is invoked)
ROOT_DIR="$(git rev-parse --show-toplevel)"
ENV_FILE="$ROOT_DIR/.env"

# Load .env if present
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

MODE="${1:-full}"
cd "$ROOT_DIR/backend"

if [[ "$MODE" == "collect" ]]; then
  exec uv run pytest --collect-only -q
else
  exec uv run pytest tests/ -x -q --tb=short
fi
```

### 2. `.pre-commit-config.yaml`

Append to the existing `local` repo's `hooks` list:

```yaml
      - id: pytest-collect
        name: pytest import check (no DB required)
        language: system
        entry: bash scripts/run-tests.sh collect
        stages: [pre-commit]
        pass_filenames: false
        files: ^backend/.*\.py$

      - id: pytest-full
        name: pytest full suite (requires postgres + redis)
        language: system
        entry: bash scripts/run-tests.sh full
        stages: [pre-push]
        pass_filenames: false
        files: ^backend/.*\.py$
```

### 3. `scripts/init-env.sh`

Append at the end (after the `echo` success line on line 87). This runs only on fresh clones (the script exits early when `.env` already exists):

```bash
# Install git hooks (both commit and push stages)
if command -v pre-commit &> /dev/null; then
  pre-commit install
  pre-commit install --hook-type pre-push
  echo "✅  pre-commit hooks installed (commit + push stages)."
fi
```

**For existing developers:** After this change is merged, run once manually:
```bash
pre-commit install --hook-type pre-push
```
This is idempotent. The CLAUDE.md "Environment Setup" section already documents `pre-commit install` as a manual step; no change needed there.

### 4. `CLAUDE.md` (project root)

In the "Execution Steps" section of "Mandatory Code Change Workflow", add after the static checks block and before the Quality Loop:

```
[REQUIRED] Run backend tests before Quality Loop:
  cd backend && uv run pytest tests/ -x -q --tb=short
  Minimum if DB unavailable: uv run pytest --collect-only -q
  Any failure → fix immediately, do not proceed
```

Add two rows to the "Common Excuses" table:

```
| "Tests pass on CI, no need to run locally"  | Must run pytest before every push         |
| "DB is not running, can't run tests"         | docker compose up -d postgres redis; then run pytest |
```

---

## Prerequisites

Before the pre-push hook can succeed, these must be in place (existing dev requirements):

1. **`.env` file** — created by `scripts/init-env.sh`; `POSTGRES_PASSWORD` must be set
2. **`jarvis_test` DB** — postgres service must be running and `uv run alembic upgrade head` must have been run at least once
3. **Docker services** — `docker compose up -d postgres redis` before `git push`

These are existing requirements already documented in `CLAUDE.md`. The hook does not automate `alembic upgrade head` — developers must keep their local `jarvis_test` DB migrated.

---

## What This Does NOT Cover

- Frontend E2E (Playwright): remains CI-only
- Non-Python file pushes: the `files: ^backend/.*\.py$` filter means the pre-push hook does not run for docs, YAML, or frontend-only changes. Those rarely affect backend tests.
- `alembic upgrade head`: not run automatically by the hook

## Success Criteria

After this change, any test failure caused by Python code changes that would fail GitHub CI's `Backend Test` job will be caught locally before `git push` completes.
