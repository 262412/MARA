from __future__ import annotations

import re
from typing import Any

_INDEXED_CITATION_RE = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


def indexed_inline_citations(
    answer: str,
    retrieved_hits: list[dict[str, Any]],
) -> list[str]:
    citations: list[str] = []
    for index in _indexed_citation_numbers(answer):
        source = _source_for_hit_index(index, retrieved_hits)
        if source and source not in citations:
            citations.append(source)
    return citations


def _indexed_citation_numbers(text: str) -> list[int]:
    indexes: list[int] = []
    for match in _INDEXED_CITATION_RE.finditer(str(text or "")):
        for item in match.group(1).split(","):
            index = int(item.strip())
            if index not in indexes:
                indexes.append(index)
    return indexes


def _source_for_hit_index(
    one_based_index: int,
    retrieved_hits: list[dict[str, Any]],
) -> str:
    if one_based_index < 1 or one_based_index > len(retrieved_hits):
        return ""
    hit = retrieved_hits[one_based_index - 1]
    for ref in hit.get("source_backrefs") or []:
        source = str(ref or "").strip()
        if source:
            return source
    source_id = str(hit.get("source_id") or hit.get("document_id") or "").strip()
    if not source_id:
        return ""
    page = str(hit.get("page_label") or "").strip()
    return f"{source_id}#page:{page}" if page else f"{source_id}#source"
