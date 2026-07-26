from __future__ import annotations

import re
from typing import Any


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
    match = re.search(
        r"(?:"
        r"\(?\s*in|"
        r"dollars?\s+(?:are\s+)?(?:presented\s+)?in|"
        r"tabular\s+dollars?\s+(?:are\s+)?(?:presented\s+)?in"
        r")\s+(thousands?|millions?|billions?)\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).lower().rstrip("s") if match else ""
