from __future__ import annotations

import re
from typing import Any

from .finance_scale import scale_from_text


def requested_scale(question: str) -> str:
    match = re.search(
        r"\b(thousand|million|billion)s?\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    return match.group(1).lower() if match else ""


def evidence_scale(text: str, item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    explicit = str(item.get("scale") or metadata.get("scale") or "").lower()
    if explicit in {"thousand", "million", "billion"}:
        return explicit
    return scale_from_text(text)
