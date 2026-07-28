from __future__ import annotations

from typing import Any


def item_metadata_text(
    item: dict[str, Any],
    metadata: dict[str, Any],
    field: str,
) -> str:
    return str(item.get(field) or metadata.get(field) or "").strip()


def retrieval_lineage_values(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    values = item.get("retrieval_lineage") or metadata.get("retrieval_lineage") or []
    return [dict(value) for value in values if isinstance(value, dict)]
