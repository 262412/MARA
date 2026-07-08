#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
SKIP_INIT="${SKIP_INIT:-0}"
INSTALL_CODEX="${INSTALL_CODEX:-0}"
INSTALL_CLAUDE_CODE="${INSTALL_CLAUDE_CODE:-0}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_CMD="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "Python 3.10+ was not found on PATH." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_KOTAEMON="$VENV_DIR/bin/kotaemon"
VENV_MARA="$VENV_DIR/bin/MARA"

"$VENV_PYTHON" -m pip install --upgrade pip

if [[ -f "$SCRIPT_DIR/libs/ktem/pyproject.toml" && -f "$SCRIPT_DIR/libs/kotaemon/pyproject.toml" ]]; then
  "$VENV_PYTHON" -m pip install "$SCRIPT_DIR/libs/ktem"
  "$VENV_PYTHON" -m pip install "$SCRIPT_DIR/libs/kotaemon[all]"
  if [[ -f "$SCRIPT_DIR/libs/slide_cli/pyproject.toml" ]]; then
    "$VENV_PYTHON" -m pip install "$SCRIPT_DIR/libs/slide_cli"
  fi
else
  "$VENV_PYTHON" -m pip install "mara-app[mara]"
fi

if [[ "$SKIP_INIT" != "1" ]]; then
  if [[ -x "$VENV_MARA" ]]; then
    "$VENV_MARA" app init
  else
    "$VENV_KOTAEMON" app init
  fi
fi

if [[ -x "$VENV_MARA" ]]; then
  "$VENV_MARA" app doctor
else
  "$VENV_KOTAEMON" app doctor
fi

if [[ "$INSTALL_CODEX" == "1" ]]; then
  if [[ -x "$VENV_MARA" ]]; then
    "$VENV_MARA" platform install --platform codex --mode full --yes
  else
    "$VENV_KOTAEMON" platform install --platform codex --mode full --yes
  fi
fi

if [[ "$INSTALL_CLAUDE_CODE" == "1" ]]; then
  if [[ -x "$VENV_MARA" ]]; then
    "$VENV_MARA" platform install --platform claude-code --mode full --yes
  else
    "$VENV_KOTAEMON" platform install --platform claude-code --mode full --yes
  fi
fi

echo
if [[ -x "$VENV_MARA" ]]; then
  echo "MARA is ready."
  echo "Run '$VENV_MARA app run' to launch the Web UI."
  echo "Run '$VENV_MARA docqa doctor' to validate the shared DocQA runtime."
  echo "Run '$VENV_MARA doctor' to validate the MARA runtime."
else
  echo "Kotaemon is ready."
  echo "Run '$VENV_KOTAEMON app run' to launch the Web UI."
  echo "Run '$VENV_KOTAEMON docqa doctor' to validate the shared DocQA runtime."
fi
