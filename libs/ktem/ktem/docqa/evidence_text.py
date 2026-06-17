from __future__ import annotations

from typing import Any

from .claim_filtering import clean_answer_text


def evidence_text(evidence_items: list[dict[str, Any]]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for item in evidence_items
        for key in ("text", "caption", "ocr_text", "vlm_text", "source_name")
    )


def extract_final_answer_text(answer: str) -> str:
    return clean_answer_text(answer)
