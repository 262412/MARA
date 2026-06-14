from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .financebench_pages import align_financebench_page


def legacy_financebench_evidence_from_source(
    value: str,
    *,
    document_id: str,
    document_path: Path | None = None,
) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not (text.startswith("{") and "evidence_" in text):
        return None
    try:
        payload = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    page = _normalize_page_value(
        _first_present(payload, "evidence_page_num", "page", "page_number")
    )
    span = str(
        payload.get("evidence_text") or payload.get("text") or payload.get("span") or ""
    ).strip()
    dataset_page = page
    page, alignment = align_financebench_page(document_path, page, span)
    citation = f"{document_id}#page:{page}" if page is not None else ""

    evidence: dict[str, Any] = {"document_id": document_id}
    if page is not None:
        evidence["page"] = page
    if alignment and dataset_page is not None:
        evidence["dataset_page"] = dataset_page
    if citation:
        evidence["citation"] = citation
    if span:
        evidence["span"] = span
    if alignment:
        evidence["page_alignment"] = alignment
    return evidence if len(evidence) > 1 else None


def _first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _normalize_page_value(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text
