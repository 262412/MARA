from __future__ import annotations

from typing import Any


def retrieval_adequacy_issue(prompt: str, evidence_metadata: dict[str, Any]) -> str:
    requirements = _financial_statement_requirements(prompt)
    if not requirements:
        return ""
    evidence_text = _combined_evidence_text(evidence_metadata).lower()
    missing = [
        label
        for label, aliases in requirements
        if not any(alias in evidence_text for alias in aliases)
    ]
    if missing:
        return (
            "Retrieved evidence lacks financial statement fields needed for "
            f"generation: {', '.join(missing)}."
        )
    if not _has_page_scoped_evidence(evidence_metadata):
        return "Retrieved evidence lacks page-scoped financial statement support."
    return ""


def _financial_statement_requirements(
    prompt: str,
) -> list[tuple[str, tuple[str, ...]]]:
    lowered = str(prompt or "").lower()
    if "quick ratio" in lowered:
        return [
            ("current assets", ("current assets", "total current assets")),
            (
                "current liabilities",
                ("current liabilities", "total current liabilities"),
            ),
            ("inventories", ("inventories", "inventory", "total inventories")),
        ]
    if "working capital" in lowered:
        return [
            ("current assets", ("current assets", "total current assets")),
            (
                "current liabilities",
                ("current liabilities", "total current liabilities"),
            ),
        ]
    if "inventory turnover" in lowered:
        return [
            ("cost of sales", ("cost of sales", "cost of goods sold", "cogs")),
            ("inventories", ("inventories", "inventory")),
        ]
    return []


def _combined_evidence_text(evidence_metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in evidence_metadata.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        metadata = _item_metadata(item)
        for key in ("text", "caption", "ocr_text", "vlm_text", "source_name"):
            parts.append(str(item.get(key) or ""))
        for key in ("page_label", "section", "table_origin"):
            parts.append(str(metadata.get(key) or ""))
    return " ".join(parts)


def _has_page_scoped_evidence(evidence_metadata: dict[str, Any]) -> bool:
    if evidence_metadata.get("page_coverage"):
        return True
    for item in evidence_metadata.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("page_label") or "").strip():
            return True
        metadata = _item_metadata(item)
        if str(metadata.get("page_label") or "").strip():
            return True
        backrefs = item.get("source_backrefs") or metadata.get("source_backrefs") or []
        if any("#page:" in str(ref) for ref in backrefs):
            return True
    return False


def _item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata
