# Pre-Push Test Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pytest as a mandatory local gate so any backend test failure is caught before `git push`, eliminating repeated GitHub CI red builds.

**Architecture:** Three layers: (1) `pre-commit` stage hook runs `pytest --collect-only` on every commit to catch import errors without needing a live DB; (2) `pre-push` stage hook runs the full test suite before every push; (3) CLAUDE.md quality loop updated to make pytest an explicit required step. Both hooks share a `scripts/run-tests.sh` wrapper that auto-loads `.env` and uses `git rev-parse --show-toplevel` for reliable path resolution.

**Tech Stack:** pre-commit framework (already installed), pytest, uv, bash

**Spec:** `docs/superpowers/specs/2026-03-24-pre-push-test-gate-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `scripts/run-tests.sh` | Loads `.env`, runs pytest in collect or full mode |
| Modify | `.pre-commit-config.yaml` | Add `pytest-collect` (pre-commit) and `pytest-full` (pre-push) hooks |
| Modify | `scripts/init-env.sh` | Append pre-push hook installation for fresh clones |
| Modify | `CLAUDE.md` | Add pytest as mandatory step in quality loop + excuses table |
| Already exists | `docs/superpowers/specs/2026-03-24-pre-push-test-gate-design.md` | Spec (commit alongside implementation) |

---

## Task 1: Create `scripts/run-tests.sh`

**Files:**
- Create: `scripts/run-tests.sh`

- [ ] **Step 1: Create the script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Find repo root unambiguously regardless of CWD or how script is invoked
ROOT_DIR="$(git rev-parse --show-toplevel)"
ENV_FILE="$ROOT_DIR/.env"

# Load .env if present (exports all vars)
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

Save to `scripts/run-tests.sh`.

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/run-tests.sh
```

- [ ] **Step 3: Verify collect mode works (no live DB needed)**

```bash
bash scripts/run-tests.sh collect
```

Expected: pytest output ending with something like `N tests collected` or no errors. Should complete in ~2 seconds. If `POSTGRES_PASSWORD` is not set, source `.env` first:
```bash
source .env && bash scripts/run-tests.sh collect
```

- [ ] **Step 4: Verify full mode works (requires postgres + redis)**

```bash
docker compose up -d postgres redis
bash scripts/run-tests.sh full
```

Expected: all tests pass (or only pre-existing failures). Should be same result as running `cd backend && uv run pytest tests/ -x -q --tb=short` directly.

---

## Task 2: Add pytest hooks to `.pre-commit-config.yaml`

**Files:**
- Modify: `.pre-commit-config.yaml`

The `local` repo block currently ends at the `mypy` hook (line 57). Append the two new hooks inside that same block.

- [ ] **Step 1: Add `pytest-collect` and `pytest-full` hooks**

In `.pre-commit-config.yaml`, find the `mypy` hook block (ends around line 57) and add after it, still inside the `local` repo's `hooks` list:

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

**Important:** `stages: [pre-push]` on `pytest-full` is mandatory — the file-level `default_stages: [pre-commit]` would otherwise suppress this hook.

- [ ] **Step 2: Install the pre-push hook type**

```bash
pre-commit install --hook-type pre-push
```

Expected output: `pre-push installed at .git/hooks/pre-push`

- [ ] **Step 3: Verify `pytest-collect` runs on commit**

Stage any `.py` file and do a dry-run:

```bash
# Touch a backend file to trigger the filter
touch backend/app/api/chat.py
git add backend/app/api/chat.py
pre-commit run pytest-collect --files backend/app/api/chat.py
git restore --staged backend/app/api/chat.py
git restore backend/app/api/chat.py
```

Expected: hook runs and exits 0 (or shows collection output).

- [ ] **Step 4: Verify `pytest-full` runs on push (dry-run)**

```bash
pre-commit run pytest-full --hook-stage pre-push --files backend/app/api/chat.py
```

Expected: full pytest suite runs and passes.

---

## Task 3: Update `scripts/init-env.sh`

**Files:**
- Modify: `scripts/init-env.sh`

- [ ] **Step 1: Append hook installation block**

At the end of `scripts/init-env.sh`, after line 87 (`echo "✅  $ENV_FILE created..."`), add:

```bash

# Install git hooks (commit + push stages)
if command -v pre-commit &> /dev/null; then
  pre-commit install
  pre-commit install --hook-type pre-push
  echo "✅  pre-commit hooks installed (commit + push stages)."
fi
```

- [ ] **Step 2: Verify the script still works end-to-end**

The script exits early at the top when `.env` already exists, so the new block only runs on fresh clones. Verify the syntax is valid:

```bash
bash -n scripts/init-env.sh
```

Expected: no output (syntax OK).

---

## Task 4: Update `CLAUDE.md` quality loop

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add pytest to mandatory static checks block**

Find the section around line 375–379:

```
[REQUIRED] Run local static checks first (tools, not agents):
【必须】先本地执行静态检查（工具层面，非 agent）：
  cd backend && uv run ruff check --fix && uv run ruff format
  cd backend && uv run mypy app
      ↓
╔══════════════════ Quality Loop
```

Replace with:

```
[REQUIRED] Run local static checks first (tools, not agents):
【必须】先本地执行静态检查（工具层面，非 agent）：
  cd backend && uv run ruff check --fix && uv run ruff format
  cd backend && uv run mypy app
      ↓
[REQUIRED] Run backend tests (catches runtime failures CI would catch):
【必须】运行后端测试（捕获 CI 会发现的运行时失败）：
  cd backend && uv run pytest tests/ -x -q --tb=short
  If DB unavailable: uv run pytest --collect-only -q (minimum)
  Any failure → fix immediately before Quality Loop
      ↓
╔══════════════════ Quality Loop
```

- [ ] **Step 2: Add two rows to the Common Excuses table**

Find the last row of the excuses table (around line 445):
```
| "code-simplifier said it looks fine" / "code-simplifier 说没问题了" | ...
```

Add after it:

```
| "Tests pass on CI, no need to run locally" / "CI 会跑测试，本地不用跑" | Must run pytest before every push / 每次 push 前必须运行 pytest |
| "DB is not running, can't run tests" / "数据库没开，无法跑测试" | `docker compose up -d postgres redis` then run pytest / 先启动再跑 |
```

---

## Task 5: Commit everything

- [ ] **Step 1: Stage all changed files**

```bash
git add \
  scripts/run-tests.sh \
  .pre-commit-config.yaml \
  scripts/init-env.sh \
  CLAUDE.md \
  docs/superpowers/specs/2026-03-24-pre-push-test-gate-design.md \
  docs/superpowers/plans/2026-03-24-pre-push-test-gate.md
```

- [ ] **Step 2: Run the quality loop**

Per CLAUDE.md mandatory workflow:

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd backend && uv run mypy app
cd backend && uv run pytest tests/ -x -q --tb=short
```

(The changed files are shell scripts, YAML, and Markdown — ruff/mypy will have nothing to flag. pytest should pass.)

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: add pre-push pytest gate to catch CI failures locally

- Add scripts/run-tests.sh: loads .env, runs pytest in collect or full mode
- Add pytest-collect hook (pre-commit stage): catches import errors, no DB needed
- Add pytest-full hook (pre-push stage): runs full test suite before every push
- Update scripts/init-env.sh: installs pre-push hook type on fresh clones
- Update CLAUDE.md: pytest is now a mandatory step in the quality loop

Existing developers must run once: pre-commit install --hook-type pre-push"
```

- [ ] **Step 4: Push**

```bash
git push origin dev
```

---

## Post-Implementation: Existing Developers

After this PR is merged, every developer (and every new Claude Code session) must run once:

```bash
pre-commit install --hook-type pre-push
```

This installs `.git/hooks/pre-push`. It is idempotent — running it multiple times is safe.

---

## Verification Checklist

- [ ] `bash scripts/run-tests.sh collect` exits 0 without a live DB
- [ ] `bash scripts/run-tests.sh full` exits 0 with postgres + redis running
- [ ] `pre-commit run pytest-collect --files backend/app/api/chat.py` runs and exits 0
- [ ] `pre-commit run pytest-full --hook-stage pre-push --files backend/app/api/chat.py` runs full suite
- [ ] Making a deliberate test failure (e.g., break an assertion) → `git push` is blocked
- [ ] Reverting the failure → `git push` succeeds
