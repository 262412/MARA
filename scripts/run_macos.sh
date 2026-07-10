#!/usr/bin/env bash
set -euo pipefail

echo "scripts/run_macos.sh is retired because it used mutable, unchecked installers." >&2
echo "From a verified source checkout, run ./install.sh and then .venv/bin/MARA app run." >&2
# The canonical path resolves KH_APP_DATA_DIR via ktem.runtime_bootstrap and
# materializes bundled assets with ktem.assets.pdfjs_assets.
exit 64
