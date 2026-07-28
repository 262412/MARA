from __future__ import annotations

import re
from typing import Any

from .evidence_representations import representation_texts


def evidence_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    late_interaction_tokens = metadata.get("late_interaction_tokens")
    late_interaction_tokens = (
        list(late_interaction_tokens)
        if isinstance(late_interaction_tokens, (list, tuple))
        else []
    )
    return " ".join(
        dict.fromkeys(
            str(value or "").strip()
            for value in (
                item.get("text"),
                item.get("ocr_text"),
                item.get("vlm_text"),
                item.get("caption"),
                item.get("row_label"),
                item.get("column_label"),
                item.get("period"),
                item.get("value"),
                item.get("unit"),
                item.get("scale"),
                item.get("currency"),
                metadata.get("section_title"),
                metadata.get("table_title"),
                *late_interaction_tokens,
                *representation_texts(item),
            )
            if str(value or "").strip()
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
