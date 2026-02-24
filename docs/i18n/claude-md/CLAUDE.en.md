[中文](../../../CLAUDE.md) | [English](CLAUDE.en.md) | [日本語](CLAUDE.ja.md) | [한국어](CLAUDE.ko.md) | [Français](CLAUDE.fr.md) | [Deutsch](CLAUDE.de.md)

# CLAUDE.md

This file provides guidance for Claude Code when working in this codebase.

## Branch Strategy

- **main**: Used only for releases. Direct commits or development are not allowed. Only accepts merges from dev or other development branches.
- **dev**: Main development branch. All daily development, bugfixes, and feature work are done on this branch or its sub-branches.
- After development is complete: dev → merge → main → push. No steps may be skipped.

## Project Overview

JARVIS is an AI assistant platform with RAG knowledge base, multi-LLM support, and streaming conversations, using a monorepo structure.

## Core Architecture

- **backend/**: FastAPI + LangGraph + SQLAlchemy (PostgreSQL) + Qdrant (vector store) + MinIO (file storage) + Redis
- **frontend/**: Vue 3 + TypeScript + Vite + Pinia
- **Root pyproject.toml**: Manages development tools only (ruff, pyright, pre-commit), no runtime dependencies
- **LLM**: Supports DeepSeek / OpenAI / Anthropic, driven by LangGraph StateGraph

## Development Environment

- **Python version**: 3.13 (`.python-version`)
- **Package manager**: `uv`
- **Virtual environment**: `.venv` (automatically managed)

## Common Commands

### Environment Setup
```bash
uv sync                      # Install all dependencies
```

### Running the Application
```bash
# Backend (in backend/ directory)
uv run uvicorn app.main:app --reload

# Frontend (in frontend/ directory)
bun run dev

# Full stack (root directory)
docker-compose up -d
```

### Code Quality Checks
```bash
ruff check                   # Code linting
ruff check --fix             # Auto-fix issues
ruff format                  # Code formatting
pyright                      # Type checking
```

### Testing
```bash
# Run in backend/ directory
uv run pytest tests/ -v                        # Run all tests
uv run pytest tests/api/test_auth.py -v        # Run a specific test file
```

### Pre-commit Hooks
```bash
pre-commit install           # Install git hooks
pre-commit run --all-files   # Manually run all hooks
```

Pre-commit automatically runs:
- YAML/TOML/JSON format checks
- uv.lock sync check
- Ruff lint and format
- Trailing newline and trailing whitespace checks

### Dependency Management
```bash
uv add <package>             # Add a production dependency
uv add --group dev <package> # Add a development dependency
uv sync --upgrade            # Update dependencies
uv lock                      # Regenerate uv.lock after manually editing pyproject.toml
```

## Tool Configuration

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **Pre-commit**: Runs uv-lock, ruff-check, ruff-format, and standard file checks

---

# Global Development Rules

## Pre-Git Operation Self-Check

**Before every `git commit`, `git push`, or commit/push skill call, you must self-check:**

```
Were files modified in this session?
   → Yes → Has the quality loop (simplifier → commit → review) been fully completed?
            → No → [STOP] Execute the quality loop immediately
            → Yes → Proceed with git operation
   → No → Are there uncommitted changes in the working tree? (git diff / git diff --cached / git stash list)
            → Yes (including stash) → [STOP] Must complete the full quality loop first
            → No → Proceed with git operation
```

---

## Mandatory Code Change Workflow

### Tool Reference

| Tool | Type | Invocation | Timing |
|------|------|-----------|--------|
| code-simplifier | Task agent | `Task` tool, `subagent_type: "code-simplifier:code-simplifier"` | Before commit |
| Pre-push code review | Skill | `Skill: superpowers:requesting-code-review` | After commit, before push |
| PR code review | Skill | `Skill: code-review:code-review --comment` | After push (requires existing PR) |

### Trigger Conditions (any one triggers the workflow)

- Any file was modified using Edit / Write / NotebookEdit
- User intends to persist changes to Git or push to remote (including expressions like "sync", "upload", "create PR", "archive", "ship", etc.)
- About to invoke any commit / push related skill

### Execution Steps (fixed order, cannot be skipped)

```
Write code / Modify files
      ↓
╔══════════════════ Quality Loop (repeat until no issues) ═════════════════╗
║                                                                          ║
║  A. [REQUIRED] Task: code-simplifier                                     ║
║     (Task agent, directly modifies files)                                ║
║          ↓                                                               ║
║  B. git add + commit                                                     ║
║     First entry → git commit                                             ║
║     Re-entry after fix → git commit --amend (keep history clean pre-push)║
║          ↓                                                               ║
║  C. [REQUIRED] Skill: superpowers:requesting-code-review                 ║
║     (Provide BASE_SHA=HEAD~1, HEAD_SHA=HEAD)                             ║
║          ↓                                                               ║
║     Issues found?                                                        ║
║       Yes → Fix code ────────────────────────────→ Back to step A        ║
║       No  ↓                                                              ║
╚══════════════════════════════════════════════════════════════════════════╝
      ↓
git push (execute immediately, do not delay)
      ↓ (if a GitHub PR exists)
[REQUIRED] Skill: code-review:code-review --comment
```

**Key Notes:**
- The quality loop must be fully executed (A→B→C) and C must have no issues before exiting
- Use `--amend` when re-entering the loop after fixes (keep a single commit before push)
- `--amend` is not a reason to skip review; C must still be re-executed

---

## Common Excuses for Skipping the Workflow (All Prohibited)

The following reasons **must not** be used to skip the workflow:

| Excuse | Correct Action |
|--------|---------------|
| "It's just a simple one-line change" | Must be executed regardless of change size |
| "The user only said commit, not review" | Commit itself is a trigger condition |
| "I just reviewed similar code" | Must re-execute after every change |
| "This is a test file / docs, not core logic" | Applies as long as Edit/Write was used to modify files |
| "Need to push before review" | Must review before push |
| "The user is rushing, commit first" | The workflow is not skipped due to urgency |
| "I'm very familiar with this code" | Familiarity does not affect workflow requirements |
| "These changes weren't made in this session" | Must execute as long as there are uncommitted changes |
| "The user didn't use the word 'commit'" | Triggers as long as the intent is to commit/push |
| "This is --amend, not a new commit" | --amend also modifies history, must execute |
| "Changes are in stash, working tree is clean" | Changes in stash also require the full workflow |
| "The user only said commit, not push" | Push must follow commit immediately, no additional instruction needed |
| "I'll push later" | Push is a required follow-up step to commit, must not be delayed |

---

## Mandatory Checkpoints

**Before executing git push**, confirm the quality loop has been fully completed:

| Step | Completion Indicator |
|------|---------------------|
| A. code-simplifier | Task agent has run, files have been organized |
| B. git add + commit/amend | All changes (including simplifier modifications) have been committed |
| C. requesting-code-review | Review found no issues, or all issues were fixed in the next iteration |

The loop must be confirmed complete before the following tool calls:

- `Bash` executing `git push`
- `Skill` calling `commit-commands:*`
- `Skill` calling `pr-review-toolkit:*` (creating a PR)

**After pushing**, if a PR exists, also execute:
- `Skill` calling `code-review:code-review --comment`

**This rule applies to all projects, without exception.**
