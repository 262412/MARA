from __future__ import annotations

import re
from typing import Any


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }


def item_tokens(item: dict[str, Any]) -> set[str]:
    return tokens(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "caption",
                "element_id",
                "modality",
                "ocr_text",
                "source_name",
                "text",
                "vlm_text",
            )
        )
    )


def metadata_tokens(item: dict[str, Any]) -> set[str]:
    metadata = dict(item.get("metadata") or {})
    values: list[Any] = [
        metadata.get("late_interaction_tokens"),
        metadata.get("visual_retriever"),
    ]
    return tokens(
        " ".join(
            str(part)
            for value in values
            for part in (value if isinstance(value, list) else [value])
        )
    )
