from __future__ import annotations

import re
from typing import Any


def evidence_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    return " ".join(
        str(value or "")
        for value in (
            item.get("text"),
            item.get("ocr_text"),
            item.get("vlm_text"),
            item.get("caption"),
            metadata.get("section_title"),
            metadata.get("table_title"),
        )
    )


def requires_multiple_operands(question: str) -> bool:
    lowered = str(question or "").lower()
    return bool(
        re.search(
            r"\b(?:ratio|difference|change|average|versus|vs\.?|compared)\b",
            lowered,
        )
        or re.search(r"\bpercentage\s+of\b|\bdivided\s+by\b", lowered)
    )
