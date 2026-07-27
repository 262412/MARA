from __future__ import annotations

import re
from typing import Any

_NUMBER_RE = re.compile(
    r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|" r"\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
)


def atomic_evidence(item: dict[str, Any]) -> bool:
    evidence_level = str(item.get("evidence_level") or "").strip().lower()
    if evidence_level == "page":
        return False
    if evidence_level == "span":
        return bool(item.get("element_id") and item.get("value") not in (None, ""))
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if not evidence_level and modality in {"table", "formula"}:
        return True
    return bool(
        item.get("cell_id")
        or item.get("table_id")
        or (item.get("element_id") and modality in {"table", "formula"})
    )


def requires_atomic_calculation_binding(item: dict[str, Any]) -> bool:
    evidence_level = str(item.get("evidence_level") or "").strip().lower()
    if evidence_level == "page":
        return True
    modality = (
        str(item.get("modality") or item.get("element_type") or "").strip().lower()
    )
    if evidence_level != "element" or modality != "table":
        return False
    text = " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )
    numeric_rows = sum(len(_NUMBER_RE.findall(line)) >= 2 for line in text.splitlines())
    return numeric_rows >= 2


def period_kind_in_question(question: str) -> str:
    lowered = str(question or "").lower()
    if re.search(
        r"\b(?:fy\s*\d{2,4}|fiscal year|full year|year end)\b",
        lowered,
    ):
        return "fiscal_year"
    if re.search(r"\b(?:quarter|three months ended)\b", lowered):
        return "quarter"
    if "twelve months ended" in lowered:
        return "fiscal_year"
    return ""


def period_kind_conflicts(
    required: str,
    item: dict[str, Any],
    text: str,
) -> bool:
    observed = str(
        item.get("period_kind") or (item.get("metadata") or {}).get("period_kind") or ""
    ).strip()
    if observed:
        return observed != required
    if required == "fiscal_year":
        return (
            ("three months ended" in text or "quarter" in text)
            and "twelve months ended" not in text
            and "fiscal year" not in text
        )
    if required == "quarter":
        return (
            ("twelve months ended" in text or "fiscal year" in text)
            and "three months ended" not in text
            and "quarter" not in text
        )
    return False
