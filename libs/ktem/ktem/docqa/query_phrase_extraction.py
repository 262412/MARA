from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_YEAR_RE = re.compile(
    r"\b(?:fy\s*)?((?:19|20)\d{2})\b|\bfy\s*(\d{2})\b",
    re.IGNORECASE,
)
_METRIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "did",
    "do",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "the",
    "to",
    "was",
    "were",
    "what",
    "which",
}


def metric_phrase(
    question: str,
    periods: list[str],
    *,
    numeric_terms: set[str],
) -> str:
    values = [
        token
        for token in _ordered_tokens(question)
        if token not in _METRIC_STOPWORDS
        and token not in numeric_terms
        and token not in set(periods)
    ]
    return " ".join(values)


def periods_in_question(question: str) -> list[str]:
    periods = list(
        dict.fromkeys(
            full or f"20{short}" for full, short in _YEAR_RE.findall(question)
        )
    )
    if len(periods) != 2 or not re.search(
        r"\b(?:from|between)\b.*\b(?:and|through|to)\b",
        question,
        flags=re.IGNORECASE,
    ):
        return periods
    start, end = (int(value) for value in periods)
    if start >= end or end - start > 10:
        return periods
    return [str(year) for year in range(start, end + 1)]


def cross_page_support_queries(question: str, fallback: str) -> tuple[str, str]:
    text = str(question or "").strip()
    compare = re.search(
        r"\bcompare\s+(.+?)\s+(?:with|to|against)\s+(.+?)(?:[?.!]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if compare:
        return (_clean_query(compare.group(1)), _clean_query(compare.group(2)))
    between = re.search(
        r"\bbetween\s+(.+?)\s+and\s+(.+?)(?:[?.!]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if between:
        return (_clean_query(between.group(1)), _clean_query(between.group(2)))
    query = text or fallback
    return query, query


def source_page_locator(item: dict[str, Any]) -> tuple[str, str]:
    metadata = dict(item.get("metadata") or {})
    return (
        str(
            item.get("source_id")
            or item.get("file_id")
            or item.get("document_id")
            or metadata.get("source_id")
            or ""
        ).strip(),
        str(
            item.get("page_label")
            or item.get("page")
            or item.get("page_number")
            or metadata.get("page_label")
            or ""
        ).strip(),
    )


def _clean_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" ,")


def _ordered_tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(str(text or ""))]
