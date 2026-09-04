from __future__ import annotations

from typing import Any


def structure_metadata_coverage(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    structured = sum(_has_structure_identity(item) for item in items)
    return round(structured / len(items), 4)


def structure_coverage_context(
    items: list[dict[str, Any]],
) -> tuple[float, float, str]:
    mixed_coverage = structure_metadata_coverage(items)
    element_index_items = [
        item
        for item in items
        if str(item.get("evidence_level") or "").strip().lower()
        in {"element", "cell", "span"}
    ]
    if not element_index_items:
        return mixed_coverage, mixed_coverage, "legacy_mixed"
    return (
        structure_metadata_coverage(element_index_items),
        mixed_coverage,
        "element_index",
    )


def _has_structure_identity(item: dict[str, Any]) -> bool:
    evidence_level = str(item.get("evidence_level") or "").strip().lower()
    return bool(
        item.get("parent_element_id")
        or item.get("neighbor_element_ids")
        or item.get("table_id")
        or item.get("continuation_id")
        or item.get("section_id")
        or (evidence_level in {"element", "cell", "span"} and item.get("element_id"))
    )
