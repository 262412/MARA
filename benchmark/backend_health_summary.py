from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_backend_health(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def backend_health_summary(backend_health: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(backend_health, dict):
        return {}
    return {
        "backend_health": dict(backend_health),
        "backend_failure_taxonomy": list(backend_health.get("failure_taxonomy") or []),
    }
