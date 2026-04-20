#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "$SCRIPT_DIR/../.venv/bin/python" ]]; then
  PYTHON_CMD="$SCRIPT_DIR/../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "Python 3.10+ was not found on PATH." >&2
  exit 1
fi

"$PYTHON_CMD" "$SCRIPT_DIR/publish_packages.py" "$@"
