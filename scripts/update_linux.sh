#!/usr/bin/env bash
set -euo pipefail

echo "scripts/update_linux.sh is retired; mutable in-place updates are unsupported." >&2
echo "Update a verified source checkout, review uv.lock, then run ./install.sh." >&2
exit 64
