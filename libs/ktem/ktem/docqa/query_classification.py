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
_BOOLEAN_QUESTION_RE = re.compile(
    r"(?:^|^[^,;:]{1,40}[,;:]\s*)(?:is|are|was|were|do|does|did|has|have|had|can|could|"
    r"will|would|should|may|might)\b",
    flags=re.IGNORECASE,
)


def has_causal_intent(tokens: set[str]) -> bool:
    return bool(tokens & _CAUSAL_TERMS)


def normalized_answer_type(
    answer_type: str,
    tokens: set[str],
    *,
    question: str = "",
    numeric_terms: set[str],
    causal_intent: bool,
) -> str:
    value = str(answer_type or "").strip().lower()
    if value in {"qa", "qasper_qa"} and _BOOLEAN_QUESTION_RE.search(question.strip()):
        return "boolean"
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
    if value in {"qa", "qasper_qa"}:
        return (
            "boolean"
            if _BOOLEAN_QUESTION_RE.search(question.strip())
            else ("free_text")
        )
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
    if answer_type == "boolean":
        return "cross_page" if requires_multiple_evidence else "simple_fact"
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
) -> dict[str, object]:
    page_numbers = re.findall(r"\bpages?\s+(\d+)|\bpage\s+(\d+)", question.lower())
    explicit_pages = {left or right for left, right in page_numbers if (left or right)}
    page_pair = re.search(
        r"\bpages?\s+(\d+)\s+(?:and|with|to|versus|vs\.?)\s+" r"(?:page\s+)?(\d+)\b",
        question,
        flags=re.IGNORECASE,
    )
    if page_pair:
        explicit_pages.update(page_pair.groups())
    ordered_pages = (
        tuple(page_pair.groups())
        if page_pair
        else tuple(
            dict.fromkeys(
                match.group(1) or match.group(2)
                for match in re.finditer(
                    r"\bpages?\s+(\d+)|\b(?:on|from)\s+page\s+(\d+)",
                    question,
                    flags=re.IGNORECASE,
                )
                if (match.group(1) or match.group(2))
            )
        )
    )
    if not ordered_pages:
        ordered_pages = tuple(sorted(explicit_pages, key=int))
    figure_match = re.search(
        r"\b(?:figure|fig\.?)\s*([A-Za-z]*\d+[A-Za-z0-9.-]*)",
        question,
        re.I,
    )
    table_match = re.search(
        r"\btable\s*([A-Za-z]*\d+[A-Za-z0-9.-]*)",
        question,
        re.I,
    )
    requires_multiple = bool(tokens & _CROSS_PAGE_TERMS) or len(explicit_pages) >= 2
    return {
        "requires_visual": bool(tokens & _VISUAL_TERMS),
        "requires_multiple_evidence": requires_multiple,
        "requires_distinct_source_pages": requires_multiple
        and (len(explicit_pages) >= 2 or "across" in tokens),
        "requires_structured_elements": bool(
            tokens & {"chart", "diagram", "figure", "formula", "plot", "table"}
        ),
        "explicit_page_labels": ordered_pages,
        "figure_label": figure_match.group(1) if figure_match else "",
        "table_label": table_match.group(1) if table_match else "",
    }
