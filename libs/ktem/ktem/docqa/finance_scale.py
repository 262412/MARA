from __future__ import annotations

import re
from typing import Any


def scale_from_text(text: str, *, aliases: tuple[str, ...] = ()) -> str:
    lowered = text.lower()
    header = re.search(
        r"(?:"
        r"\(?\s*in|"
        r"dollars?\s+(?:are\s+)?(?:presented\s+)?in|"
        r"tabular\s+dollars?\s+(?:are\s+)?(?:presented\s+)?in"
        r")\s+(thousands?|millions?|billions?)\b|"
        r"\(\s*(thousands?|millions?|billions?)\s*\)",
        lowered,
    )
    if header is not None:
        return next(value for value in header.groups() if value).rstrip("s")
    for alias in aliases:
        match = re.search(
            rf"{re.escape(alias.lower())}.{{0,100}}?"
            r"(thousands?|millions?|billions?)\b",
            lowered,
        )
        if match is not None:
            return match.group(1).rstrip("s")
    return ""


def source_scale_evidence(
    item: dict[str, Any] | None,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, str]:
    source_id = _source_id(item)
    if not source_id:
        return "", ""
    item_id = _item_id(item)
    matches: list[tuple[int, str, str]] = []
    for candidate in evidence_items:
        if _source_id(candidate) != source_id:
            continue
        if (
            _is_atomic_evidence(candidate)
            and _item_id(candidate) != item_id
            and candidate.get("value") not in (None, "")
        ):
            continue
        scale = _item_dimension(candidate, "scale") or scale_from_text(
            _item_text(candidate)
        )
        evidence_id = _item_id(candidate)
        if scale and evidence_id:
            matches.append((_binding_distance(item, candidate), scale, evidence_id))
    if not matches:
        return "", ""
    best_distance = min(distance for distance, _scale, _evidence_id in matches)
    local_matches = [
        (scale, evidence_id)
        for distance, scale, evidence_id in matches
        if distance == best_distance
    ]
    scales = {scale for scale, _evidence_id in local_matches}
    if len(scales) != 1:
        return "", ""
    scale = next(iter(scales))
    evidence_id = next(
        evidence_id
        for candidate_scale, evidence_id in local_matches
        if candidate_scale == scale
    )
    if item is not None and evidence_id == _item_id(item):
        return scale, ""
    return scale, evidence_id


def dimension_binding_scope(
    item: dict[str, Any] | None,
    dimension_item: dict[str, Any] | None,
) -> str:
    if item is None or dimension_item is None:
        return ""
    if _same_field(item, dimension_item, "table_instance_id"):
        return "table"
    if _same_field(item, dimension_item, "table_group_id"):
        return "table_group"
    if _same_field(item, dimension_item, "page_label"):
        return "page"
    if _source_id(item) == _source_id(dimension_item):
        return "source"
    return ""


def compatible_dimension_scope(
    item: dict[str, Any],
    dimension_item: dict[str, Any],
) -> bool:
    if _source_id(item) != _source_id(dimension_item):
        return False
    table_instance_id = _item_dimension(item, "table_instance_id")
    dimension_table_instance_id = _item_dimension(
        dimension_item,
        "table_instance_id",
    )
    if table_instance_id and dimension_table_instance_id:
        return table_instance_id == dimension_table_instance_id
    table_group_id = _item_dimension(item, "table_group_id")
    dimension_table_group_id = _item_dimension(dimension_item, "table_group_id")
    if table_group_id and dimension_table_group_id:
        return table_group_id == dimension_table_group_id
    return True


def _binding_distance(
    item: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> int:
    scope = dimension_binding_scope(item, candidate)
    return {
        "table": 0,
        "table_group": 1,
        "page": 2,
        "source": 3,
    }.get(scope, 4)


def _same_field(
    left: dict[str, Any],
    right: dict[str, Any],
    field: str,
) -> bool:
    left_value = _item_dimension(left, field)
    right_value = _item_dimension(right, field)
    return bool(left_value and left_value == right_value)


def _item_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return str(
        item.get("evidence_id")
        or item.get("element_id")
        or item.get("canonical_id")
        or ""
    ).strip()


def _source_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    metadata = dict(item.get("metadata") or {})
    return str(
        item.get("source_id")
        or item.get("file_id")
        or item.get("document_id")
        or metadata.get("source_id")
        or ""
    ).strip()


def _item_text(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def _item_dimension(item: dict[str, Any] | None, field: str) -> str:
    if item is None:
        return ""
    metadata = dict(item.get("metadata") or {})
    return str(item.get(field) or metadata.get(field) or "").strip()


def _is_atomic_evidence(item: dict[str, Any]) -> bool:
    return str(item.get("evidence_level") or "").strip().lower() in {"cell", "span"}
