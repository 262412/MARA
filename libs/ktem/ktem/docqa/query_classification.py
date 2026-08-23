from __future__ import annotations

import re

from .query_phrase_extraction import cross_page_support_queries

_LONG_FORM_TERMS = {"describe", "explain", "how", "summarize", "why"}
_DESCRIPTIVE_ANSWER_TYPES = {
    "descriptive",
    "long_form",
    "long-form",
    "narrative",
    "text",
}
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
    "between",
    "compare",
    "comparison",
    "jointly",
    "versus",
    "vs",
}
_SOURCE_COLLECTION_TERMS = {
    "document",
    "documents",
    "paper",
    "papers",
    "report",
    "reports",
    "source",
    "sources",
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
_VISUAL_REFERENCE = (
    r"(?:images?|fig(?:ures?)?\.?|charts?|diagrams?|plots?|slides?|visuals?|tables?)"
)
_VISUAL_READING_ACTION = (
    r"(?:show(?:s|n|ing)?|display(?:s|ed|ing)?|depict(?:s|ed|ing)?|"
    r"illustrat(?:e|es|ed|ing)|contain(?:s|ed|ing)?|include(?:s|d|ing)?|"
    r"represent(?:s|ed|ing)?|(?:indicate(?:s|d)?|indicating)|reveal(?:s|ed|ing)?|"
    r"visible|appear(?:s|ed|ing)?|look(?:s|ed|ing)?|read(?:s|ing)?)"
)
_VISUAL_DETAIL = (
    r"(?:color|colour|shape|position|location|label|labels|marker|markers|"
    r"region|regions|object|objects|pixel|pixels|axis|axes|bar|bars|line|"
    r"lines|curve|curves|outlier|outliers|trend|trends)"
)
_VISUAL_CONTENT_RELATION = (
    r"(?:highest|lowest|longest|shortest|largest|smallest|leftmost|rightmost|"
    r"above|below|between|near|behind|foreground|background|positioned|"
    r"aligned|located)"
)
_VISUAL_NON_CONTENT_FOLLOWER = (
    r"(?:models?|encoders?|feature|features|representations?|"
    r"experiments?|methods?|branches?|modules?|networks?|embeddings?|"
    r"datasets?|domains?|data|inputs?|outputs?|classifications?|recognitions?)"
)
_VISUAL_CONTENT_QUERY_RE = re.compile(
    rf"\b(?:what|which|where|who|how many|how much|is|are|was|were|"
    rf"does|do|did|can|could)\b.*?(?:"
    rf"\b{_VISUAL_REFERENCE}\b.*?\b{_VISUAL_READING_ACTION}\b|"
    rf"\b{_VISUAL_READING_ACTION}\b.*?\b{_VISUAL_REFERENCE}\b|"
    rf"\b(?:in|on|from|within|inside)\s+(?:the\s+)?"
    rf"\b{_VISUAL_REFERENCE}\b|"
    rf"\b{_VISUAL_DETAIL}\b.*?\b{_VISUAL_CONTENT_RELATION}\b.*?"
    rf"\b{_VISUAL_REFERENCE}\b|"
    rf"\b{_VISUAL_REFERENCE}\b.*?\b{_VISUAL_CONTENT_RELATION}\b.*?"
    rf"\b{_VISUAL_DETAIL}\b)",
    flags=re.IGNORECASE,
)
_VISUAL_INSPECTION_QUERY_RE = re.compile(
    rf"\b(?:according\s+to|based\s+on)\s+(?:the\s+)?\b{_VISUAL_REFERENCE}\b|"
    rf"\b(?:explain|summarize|analyse|analyze|interpret)\b\s+"
    rf"(?:the\s+)?(?:[a-z0-9_-]+\s+){{0,3}}\b{_VISUAL_REFERENCE}\b|"
    rf"\b(?:describe|identify|inspect|read|locate|count|list|name|"
    rf"transcribe)\b\s+(?:the\s+)?\b{_VISUAL_REFERENCE}\b|"
    rf"\b(?:describe|identify|inspect|read|locate|count|list|name|"
    rf"transcribe)\b.*?\b(?:in|on|from|within|inside)\s+(?:the\s+)?"
    rf"\b{_VISUAL_REFERENCE}\b",
    flags=re.IGNORECASE,
)
_VISUAL_NON_CONTENT_REFERENCE_RE = re.compile(
    rf"\b{_VISUAL_REFERENCE}\b\s+{_VISUAL_NON_CONTENT_FOLLOWER}\b",
    flags=re.IGNORECASE,
)
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
    if value in _DESCRIPTIVE_ANSWER_TYPES:
        value = "free_text"
    if value in {
        "evidence_qa",
        "qa",
        "qasper_qa",
        "extractive",
        "span",
        "short_answer",
        "multiple_choice",
    } and _BOOLEAN_QUESTION_RE.search(question.strip()):
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
    if value in {"evidence_qa", "qa", "qasper_qa"}:
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
    requires_visual: bool = False,
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
    if requires_visual:
        return "visual"
    if tokens & _LONG_FORM_TERMS:
        return "long_form"
    return "simple_fact"


def question_capabilities(
    question: str,
    tokens: set[str],
    *,
    boolean_question: bool = False,
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
    # ``across`` is commonly semantic (for example, across languages or
    # datasets).  Only explicit page locators or comparison terms establish a
    # physical multi-evidence requirement.
    left_query, right_query = cross_page_support_queries(question, "")
    distinct_subjects = bool(
        left_query
        and right_query
        and " ".join(left_query.lower().split())
        != " ".join(right_query.lower().split())
    )
    source_collection_comparison = bool(
        tokens & {"compare", "comparison"} and tokens & _SOURCE_COLLECTION_TERMS
    )
    generic_comparison = bool(tokens & {"compare", "comparison"}) and not (
        boolean_question
    )
    requires_multiple = len(explicit_pages) >= 2 or bool(
        (tokens & _CROSS_PAGE_TERMS and distinct_subjects)
        or source_collection_comparison
        or generic_comparison
    )
    return {
        "requires_visual": _requires_visual_content(question, tokens),
        "requires_multiple_evidence": requires_multiple,
        "requires_distinct_source_pages": requires_multiple
        and len(explicit_pages) >= 2,
        "requires_structured_elements": bool(
            tokens & {"chart", "diagram", "figure", "formula", "plot", "table"}
        ),
        "explicit_page_labels": ordered_pages,
        "figure_label": figure_match.group(1) if figure_match else "",
        "table_label": table_match.group(1) if table_match else "",
    }


def _requires_visual_content(question: str, tokens: set[str]) -> bool:
    """Require visual evidence only for questions that inspect visual content."""

    text = str(question or "").strip()
    if not text or not (
        tokens & _VISUAL_TERMS
        or re.search(rf"\b{_VISUAL_REFERENCE}\b", text, re.IGNORECASE)
    ):
        return False
    if _all_visual_references_are_non_content(text):
        return False
    visual_references = list(
        re.finditer(rf"\b{_VISUAL_REFERENCE}\b", text, re.IGNORECASE)
    )
    if len(visual_references) >= 2 and tokens & _CROSS_PAGE_TERMS:
        return True
    return bool(
        _VISUAL_CONTENT_QUERY_RE.search(text)
        or _VISUAL_INSPECTION_QUERY_RE.search(text)
    )


def _all_visual_references_are_non_content(text: str) -> bool:
    references = list(re.finditer(rf"\b{_VISUAL_REFERENCE}\b", text, re.IGNORECASE))
    return bool(references) and all(
        _VISUAL_NON_CONTENT_REFERENCE_RE.match(text, match.start())
        for match in references
    )
