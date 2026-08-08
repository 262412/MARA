from __future__ import annotations

import re
from typing import Any

MODALITY_TERMS = {
    "page_image": {"chart", "diagram", "figure", "image", "plot", "slide", "visual"},
    "figure": {"chart", "diagram", "figure", "image", "plot", "visual"},
    "formula": {"equation", "formula", "latex", "math"},
    "slide": {"deck", "presentation", "ppt", "pptx", "slide"},
    "table": {"column", "row", "table"},
}


def modality_intent_score(query: str, modality: str) -> float:
    return 0.5 if tokens(query) & MODALITY_TERMS.get(modality, set()) else 0.0


def item_tokens(item: dict[str, Any]) -> set[str]:
    return tokens(item_text(item))


def item_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    metadata_text = " ".join(
        str(part)
        for value in metadata.values()
        for part in (value if isinstance(value, list) else [value])
    )
    fields = (
        "caption",
        "element_id",
        "modality",
        "ocr_text",
        "source_name",
        "text",
        "vlm_text",
    )
    return " ".join(str(item.get(key) or "") for key in fields) + " " + metadata_text


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
