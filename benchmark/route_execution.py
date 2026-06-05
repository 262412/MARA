from __future__ import annotations

from typing import Any

from ktem.docqa.visual_backends import visual_backend_health


def route_skip_record(
    route: dict[str, Any],
    *,
    route_id: str,
    engine: str,
) -> dict[str, Any] | None:
    backend_status = str(route.get("backend_status") or "").strip()
    missing_backends = [
        str(item).strip()
        for item in route.get("missing_backends", []) or []
        if str(item).strip()
    ]
    requires_backend_config = _bool_value(route.get("requires_backend_config"))
    if requires_backend_config and not missing_backends:
        health = visual_backend_health(route)
        missing_backends = list(health.get("missing_backends") or [])
        if missing_backends:
            backend_status = str(health.get("backend_status") or "not_configured")
    if backend_status != "not_configured" and not (
        requires_backend_config and missing_backends
    ):
        return None

    return {
        "route_id": route_id,
        "engine": engine,
        "backend_status": backend_status or "not_configured",
        "requires_backend_config": requires_backend_config,
        "missing_backends": missing_backends,
        "skip_reason": _skip_reason(missing_backends),
    }


def _skip_reason(missing_backends: list[str]) -> str:
    if missing_backends:
        return f"not_configured: {', '.join(missing_backends)}"
    return "not_configured"


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)
