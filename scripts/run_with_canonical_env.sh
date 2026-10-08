#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
BOOTSTRAP_PYTHON=python3
case "$(uname -s)" in
  MINGW*|MSYS*) BOOTSTRAP_PYTHON=python ;;
esac
"$BOOTSTRAP_PYTHON" "$SCRIPT_DIR/check_mara_worktree_env.py" check >/dev/null
CANONICAL_VENV="$("$BOOTSTRAP_PYTHON" "$SCRIPT_DIR/check_mara_worktree_env.py" canonical-venv)"
if command -v cygpath >/dev/null 2>&1; then
  CANONICAL_VENV="$(cygpath -u "$CANONICAL_VENV")"
fi

export PYTHONPATH="$PROJECT_ROOT/libs/slide_cli:$PROJECT_ROOT/libs/ktem:$PROJECT_ROOT/libs/kotaemon${PYTHONPATH:+:$PYTHONPATH}"
CANONICAL_PYTHON="$CANONICAL_VENV/bin/python"
if [[ -f "$CANONICAL_VENV/Scripts/python.exe" ]]; then
  CANONICAL_PYTHON="$CANONICAL_VENV/Scripts/python.exe"
fi
exec "$CANONICAL_PYTHON" "$@"
