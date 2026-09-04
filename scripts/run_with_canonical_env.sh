#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
python3 "$SCRIPT_DIR/check_mara_worktree_env.py" check >/dev/null
CANONICAL_VENV="$(python3 "$SCRIPT_DIR/check_mara_worktree_env.py" canonical-venv)"

export PYTHONPATH="$PROJECT_ROOT/libs/slide_cli:$PROJECT_ROOT/libs/ktem:$PROJECT_ROOT/libs/kotaemon${PYTHONPATH:+:$PYTHONPATH}"
exec "$CANONICAL_VENV/bin/python" "$@"
