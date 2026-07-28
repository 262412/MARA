from __future__ import annotations

import re

_LONG_FORM_TERMS = {"describe", "explain", "how", "summarize", "why"}
_CAUSAL_TERMS = {
    "cause",
    "caused",
    "causes",
    "driver",
    "drivers",
    "drove",
    "factor",
    "factors",
    "reason",
    "reasons",
    "why",
}
_CROSS_PAGE_TERMS = {
    "across",
    "between",
    "compare",
    "comparison",
    "jointly",
    "versus",
    "vs",
}
_VISUAL_TERMS = {
    "chart",
    "diagram",
    "figure",
    "image",
    "plot",
    "slide",
    "table",
    "visual",
}


def has_causal_intent(tokens: set[str]) -> bool:
    return bool(tokens & _CAUSAL_TERMS)


def normalized_answer_type(
    answer_type: str,
    tokens: set[str],
    *,
    numeric_terms: set[str],
    causal_intent: bool,
) -> str:
    value = str(answer_type or "").strip().lower()
    if causal_intent:
        return (
            value
            if value and value not in {"numeric", "number", "calculation"}
            else "free_text"
        )
    if value in {"numeric", "number", "calculation", "percentage", "ratio"}:
        return "numeric"
    if value in {"boolean", "free_text", "formula", "list", "unanswerable"}:
        return value
    if tokens & numeric_terms:
        return "numeric"
    return value or "free_text"


def question_type(
    tokens: set[str],
    answer_type: str,
    periods: list[str],
    *,
    causal_intent: bool,
    requires_multiple_evidence: bool,
) -> str:
    if causal_intent:
        return "long_form"
    if answer_type == "numeric" and len(periods) >= 2:
        return "multi_period_numeric"
    if answer_type == "numeric":
        return "numeric"
    if requires_multiple_evidence:
        return "cross_page"
    if tokens & _VISUAL_TERMS:
        return "visual"
    if tokens & _CROSS_PAGE_TERMS:
        return "cross_page"
    if tokens & _LONG_FORM_TERMS:
        return "long_form"
    return "simple_fact"


def question_capabilities(
    question: str,
    tokens: set[str],
) -> dict[str, bool]:
    page_numbers = re.findall(r"\bpages?\s+(\d+)|\bpage\s+(\d+)", question.lower())
    explicit_pages = {
        left or right for left, right in page_numbers if (left or right)
    }
    page_pair = re.search(
        r"\bpages?\s+(\d+)\s+(?:and|with|to|versus|vs\.?)\s+"
        r"(?:page\s+)?(\d+)\b",
        question,
        flags=re.IGNORECASE,
    )
    if page_pair:
        explicit_pages.update(page_pair.groups())
    requires_multiple = bool(tokens & _CROSS_PAGE_TERMS) or len(explicit_pages) >= 2
    return {
        "requires_visual": bool(tokens & _VISUAL_TERMS),
        "requires_multiple_evidence": requires_multiple,
        "requires_distinct_source_pages": requires_multiple
        and (len(explicit_pages) >= 2 or "across" in tokens),
        "requires_structured_elements": bool(
            tokens & {"chart", "diagram", "figure", "formula", "plot", "table"}
        ),
    }
