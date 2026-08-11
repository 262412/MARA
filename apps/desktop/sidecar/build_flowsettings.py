from __future__ import annotations

import os
from pathlib import Path

from theflow.settings.default import *  # noqa: F401,F403

build_runtime_value = str(
    os.environ.get("MARA_DESKTOP_BUILD_RUNTIME_ROOT", "") or ""
).strip()
if not build_runtime_value:
    raise RuntimeError("MARA_DESKTOP_BUILD_RUNTIME_ROOT is required")

build_runtime_root = Path(build_runtime_value).expanduser().resolve()
CACHE = {  # noqa: F405
    "__type__": "theflow.cache.FileCache",
    "path": str(build_runtime_root / "cache" / "components"),
}
STORAGE = {  # noqa: F405
    "__type__": "theflow.storage.LocalStorage",
    "prefix": str(build_runtime_root / "cache" / "theflow"),
}
