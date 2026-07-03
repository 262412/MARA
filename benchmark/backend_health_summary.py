from __future__ import annotations

from typing import Any


def backend_health_summary(backend_health: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(backend_health, dict):
        return {}
    return {
        "backend_health": dict(backend_health),
        "backend_failure_taxonomy": list(backend_health.get("failure_taxonomy") or []),
    }
