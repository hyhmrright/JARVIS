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

case "$MODE" in
  collect) exec uv run pytest --collect-only -q ;;
  full)    exec uv run pytest tests/ -x -q --tb=short ;;
  *) echo "Usage: $0 [collect|full]" >&2; exit 1 ;;
esac
