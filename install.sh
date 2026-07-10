#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-3.10}"
SKIP_INIT="${SKIP_INIT:-0}"
INSTALL_CODEX="${INSTALL_CODEX:-0}"
INSTALL_CLAUDE_CODE="${INSTALL_CLAUDE_CODE:-0}"

if [[ ! -f "$SCRIPT_DIR/pyproject.toml" || ! -f "$SCRIPT_DIR/uv.lock" ]]; then
  echo "install.sh supports a verified MARA source checkout with uv.lock." >&2
  exit 64
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install a verified uv release with your package manager." >&2
  exit 69
fi
export UV_PYTHON_DOWNLOADS=never
if ! uv python find "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "A local Python $PYTHON_BIN interpreter is required; automatic downloads are disabled." >&2
  exit 69
fi

export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
uv sync \
  --project "$SCRIPT_DIR" \
  --frozen \
  --no-dev \
  --extra mara \
  --python "$PYTHON_BIN"

VENV_MARA="$VENV_DIR/bin/MARA"
if [[ ! -x "$VENV_MARA" ]]; then
  echo "The frozen sync did not create $VENV_MARA." >&2
  exit 70
fi

if [[ "$SKIP_INIT" != "1" ]]; then
  "$VENV_MARA" app init
fi
"$VENV_MARA" app doctor

if [[ "$INSTALL_CODEX" == "1" ]]; then
  "$VENV_MARA" platform install --platform codex --mode full --yes
fi
if [[ "$INSTALL_CLAUDE_CODE" == "1" ]]; then
  "$VENV_MARA" platform install --platform claude-code --mode full --yes
fi

echo
echo "MARA is ready."
echo "Run '$VENV_MARA app run' to launch the Web UI."
echo "Run '$VENV_MARA docqa doctor' to validate the shared DocQA runtime."
echo "Run '$VENV_MARA doctor' to validate the MARA runtime."
