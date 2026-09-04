from __future__ import annotations

import os
from pathlib import Path

build_runtime_value = str(
    os.environ.get("MARA_DESKTOP_BUILD_RUNTIME_ROOT", "") or ""
).strip()
if not build_runtime_value:
    raise RuntimeError("MARA_DESKTOP_BUILD_RUNTIME_ROOT is required")

build_runtime_root = Path(build_runtime_value).expanduser().resolve()
CONTEXT = {
    "__type__": "theflow.context.Context",
}
CACHE = {
    "__type__": "theflow.cache.FileCache",
    "path": str(build_runtime_root / "cache" / "components"),
}
STORAGE = {
    "__type__": "theflow.storage.LocalStorage",
    "prefix": str(build_runtime_root / "cache" / "theflow"),
}
MIDDLEWARE = {
    "default": [
        "theflow.middleware.TrackProgressMiddleware",
        "theflow.middleware.CachingMiddleware",
        "theflow.middleware.SkipComponentMiddleware",
    ]
}
BASE_BACKEND = {
    "__type__": "theflow.backends.Backend",
}
