from __future__ import annotations

_FocusRule = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]

_FOCUS_RULES: tuple[_FocusRule, ...] = (
    (
        (),
        ("primary customers", "customer base"),
        (
            "limited number of commercial airlines",
            "revenues from a limited number",
            "U.S. government contracts",
            "percent of revenues",
        ),
    ),
    (
        (),
        ("customer concentration", "major customer"),
        (
            "one customer accounted for",
            "consolidated net revenue",
            "major customer",
        ),
    ),
    (
        (),
        ("retiree", "retirees", "future benefit payments"),
        (
            "Estimated Future Benefit Payments",
            "Pension Benefits",
            "Health Care and Life",
        ),
    ),
    (
        (),
        ("acquisition", "acquisitions", "acquired"),
        (
            "Note Acquisitions",
            "wholly owned subsidiary",
            "acquired all outstanding shares",
        ),
    ),
    (
        (),
        ("what industry", "primarily operate", "industry does"),
        ("Item 1 Business", "company overview", "global leader"),
    ),
    (
        (),
        ("gross margin",),
        ("Total revenues", "Total costs and expenses", "Gross profit"),
    ),
    (
        (),
        ("debt securities", "national securities exchange"),
        ("Section 12(b)", "Section 12(g)", "None"),
    ),
)


def finance_retrieval_focus_terms(question: str) -> tuple[str, ...]:
    normalized = str(question or "").lower()
    terms: list[str] = []
    for required, alternatives, focus in _FOCUS_RULES:
        if all(term in normalized for term in required) and any(
            term in normalized for term in alternatives
        ):
            terms.extend(term for term in focus if term not in terms)
    return tuple(terms)


def finance_retrieval_query(question: str) -> str:
    focus = finance_retrieval_focus_terms(question)
    if not focus:
        return str(question or "")
    return " ".join((str(question or "").strip(), *focus)).strip()
