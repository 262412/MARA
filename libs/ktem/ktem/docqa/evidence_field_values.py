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


def representation_values(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    values = item.get("representations") or metadata.get("representations") or []
    return [dict(value) for value in values if isinstance(value, dict)]


def atomic_identity_fields(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        field: str(item.get(field) or metadata.get(field) or "").strip()
        for field in ("cell_id", "span_id")
    }


def visual_evidence_fields(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "figure_label": item_metadata_text(item, metadata, "figure_label"),
        "table_label": item_metadata_text(item, metadata, "table_label"),
        "bbox": item.get("bbox", metadata.get("bbox")),
        "caption": item_metadata_text(item, metadata, "caption"),
        "ocr_text": item_metadata_text(item, metadata, "ocr_text"),
        "vlm_text": item_metadata_text(item, metadata, "vlm_text"),
        "representations": representation_values(item, metadata),
    }


def score_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
