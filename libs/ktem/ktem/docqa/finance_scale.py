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
        r")\s+(thousands?|millions?|billions?)\b",
        lowered,
    )
    if header is not None:
        return header.group(1).rstrip("s")
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
    matches: list[tuple[str, str]] = []
    for candidate in evidence_items:
        if _source_id(candidate) != source_id:
            continue
        scale = _item_dimension(candidate, "scale") or scale_from_text(
            _item_text(candidate)
        )
        evidence_id = _item_id(candidate)
        if scale and evidence_id:
            matches.append((scale, evidence_id))
    scales = {scale for scale, _evidence_id in matches}
    if len(scales) != 1:
        return "", ""
    scale = next(iter(scales))
    evidence_id = next(
        evidence_id
        for candidate_scale, evidence_id in matches
        if candidate_scale == scale
    )
    if item is not None and evidence_id == _item_id(item):
        return scale, ""
    return scale, evidence_id


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
