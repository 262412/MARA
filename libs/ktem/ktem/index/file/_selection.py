from __future__ import annotations

import json
from typing import Any


def normalize_selected_values(selected: Any) -> list[str]:
    if selected in (None, ""):
        return []

    values = selected if isinstance(selected, (list, tuple, set)) else [selected]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        _append_selected_value(value, normalized, seen)
    return normalized


def owner_scope_required(app: Any, config: dict[str, Any]) -> bool:
    return bool(config.get("private") or getattr(app, "f_user_management", False))


def _append_selected_value(
    value: Any,
    normalized: list[str],
    seen: set[str],
) -> None:
    if value in (None, "") or isinstance(value, dict):
        return
    if isinstance(value, (list, tuple, set)):
        _append_unique(normalize_selected_values(list(value)), normalized, seen)
        return

    item = str(value).strip()
    if not item:
        return
    if item.startswith("[") and item.endswith("]"):
        try:
            decoded = json.loads(item)
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, list):
            _append_unique(normalize_selected_values(decoded), normalized, seen)
            return
    _append_unique([item], normalized, seen)


def _append_unique(
    values: list[str],
    normalized: list[str],
    seen: set[str],
) -> None:
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)


__all__ = ["normalize_selected_values", "owner_scope_required"]
