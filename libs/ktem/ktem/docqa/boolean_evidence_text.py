from __future__ import annotations

import re
from typing import Any

from .boolean_scope_alternatives import expanded_alternative_quote


def _normalized(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def evidence_item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _scope_quote(question: str, item: dict[str, Any], quote: str) -> str:
    return expanded_alternative_quote(question, evidence_item_text(item), quote)


def _matching_item(
    quote: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_quote = _normalized(quote)
    for item in items:
        text = _normalized(evidence_item_text(item))
        if normalized_quote and normalized_quote in text:
            return item
    return {}


def _bound_local_context(item: dict[str, Any], quote: str) -> str:
    text = evidence_item_text(item)
    normalized_quote = _normalized(quote)
    if not text or not normalized_quote:
        return str(quote or "")
    normalized_text = _normalized(text)
    if normalized_quote not in normalized_text:
        return str(quote or "")
    parts = str(quote or "").strip().split()
    pattern = re.compile(
        r"\s+".join(re.escape(part) for part in parts),
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if match is None:
        return str(quote or "")
    heading = _nearest_heading(item, quote)
    start = max(0, match.start() - 320)
    end = min(len(text), match.end() + 320)
    return "\n".join(part for part in (heading, text[start:end]) if part)


def _nearest_heading(item: dict[str, Any], quote: str) -> str:
    text = evidence_item_text(item)
    if not text:
        return ""
    parts = str(quote or "").strip().split()
    if not parts:
        return ""
    match = re.search(
        r"\s+".join(re.escape(part) for part in parts),
        text,
        flags=re.IGNORECASE,
    )
    prefix = text[: match.start()] if match is not None else text
    headings = re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$", prefix)
    return headings[-1].strip() if headings else ""
