from __future__ import annotations

from typing import Any


def config_value(config: Any, key: str, default: Any) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def field_value(item: Any, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def active_runtime_record(runtime: Any, selected_file_ids: list[str]) -> Any | None:
    if not selected_file_ids:
        return None
    try:
        records = runtime.resolve_file_refs([selected_file_ids[0]])
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return records[0] if records else None
