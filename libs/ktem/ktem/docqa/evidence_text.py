from __future__ import annotations

from typing import Any

from .claim_filtering import clean_answer_text


def evidence_text(evidence_items: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for item in evidence_items:
        block = "\n".join(
            str(item.get(key) or "").strip()
            for key in ("text", "caption", "ocr_text", "vlm_text", "source_name")
            if str(item.get(key) or "").strip()
        )
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def extract_final_answer_text(answer: str) -> str:
    return clean_answer_text(answer)
