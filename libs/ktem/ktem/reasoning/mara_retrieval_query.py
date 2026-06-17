from __future__ import annotations

ANSWER_FORMAT_MARKER = "\n\nAnswer formatting requirements:"
_GENERIC_STRUCTURED_CALCULATION_TERMS = (
    "average",
    "calculate",
    "calculation",
    "change",
    "count",
    "difference",
    "margin",
    "percentage",
    "rate",
    "ratio",
    "sum",
    "total",
)
_GENERIC_STRUCTURED_CALCULATION_CONTEXT_TERMS = (
    "based on",
    "from the table",
    "in the table",
    "using the",
)
_GENERIC_STRUCTURED_CALCULATION_FOCUS = (
    "source table",
    "formula inputs",
    "row labels",
    "column labels",
    "component values",
    "totals",
)
_FINANCE_FOCUS_RULES: tuple[
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    ...,
] = (
    (
        (),
        ("quick ratio",),
        (
            "Consolidated Balance Sheet",
            "Total current assets",
            "Total current liabilities",
            "Inventories",
            "Cash and cash equivalents",
            "Marketable securities",
            "Accounts receivable",
        ),
    ),
    (
        (),
        ("working capital",),
        (
            "Consolidated Balance Sheet",
            "Total current assets",
            "Total current liabilities",
            "Current assets",
            "Current liabilities",
        ),
    ),
    (
        (),
        ("inventory turnover",),
        (
            "Consolidated Statement of Income",
            "Consolidated Balance Sheet",
            "Cost of sales",
            "Cost of goods sold",
            "Inventories",
        ),
    ),
    (
        (),
        ("capital expenditure", "capex", "cash flow"),
        (
            "Consolidated Statement of Cash Flows",
            "Capital expenditures",
            "Purchases of property, plant and equipment",
            "Net cash provided by operating activities",
        ),
    ),
    (
        (),
        ("ppne", "pp&e", "ppe", "fixed asset"),
        (
            "Consolidated Balance Sheet",
            "Property, plant and equipment",
            "Property and equipment",
            "Accumulated depreciation",
            "Total assets",
        ),
    ),
    (
        (),
        ("capital-intensive", "capital intensive", "capital intensity"),
        (
            "Consolidated Statement of Income",
            "Consolidated Balance Sheet",
            "Consolidated Statement of Cash Flows",
            "Net sales",
            "Property, plant and equipment",
            "Capital expenditures",
            "Total assets",
        ),
    ),
    (
        (),
        ("net ar", "accounts receivable", "trade receivables", "receivables"),
        (
            "Consolidated Balance Sheet",
            "Trade receivables, net",
            "Accounts receivable",
            "Receivables, net",
            "Current assets",
        ),
    ),
    (
        (),
        ("days payable outstanding", "dpo", "accounts payable"),
        (
            "Consolidated Statements of Income",
            "Consolidated Balance Sheets",
            "Accounts payable",
            "Cost of sales",
            "Inventories",
            "Net sales",
        ),
    ),
    (
        (),
        ("restructuring cost", "restructuring costs"),
        (
            "Consolidated Statements of Operations",
            "Consolidated Statement of Operations",
            "Income statements",
            "Restructuring costs",
            "Operating income",
        ),
    ),
    (
        (),
        ("operating margin", "gross margin"),
        (
            "Consolidated Statement of Income",
            "Net sales",
            "Operating income",
            "Gross profit",
            "Selling, general and administrative",
        ),
    ),
    (
        (),
        ("primary customers", "customers", "customer base"),
        (
            "customers",
            "commercial airlines",
            "U.S. government contracts",
            "revenues from a limited number",
            "substantial portion of our revenue",
        ),
    ),
    (
        (),
        ("geographies", "geography", "geographic", "operates in", "regions"),
        (
            "geographic regions",
            "United States",
            "EMEA",
            "APAC",
            "LACC",
            "Total revenues net of interest expense",
        ),
    ),
    (
        ("segment",),
        ("m&a", "acquisition", "divestiture", "organic", "growth"),
        (
            "Worldwide Sales Change",
            "Business Segment",
            "Organic sales",
            "Acquisitions",
            "Divestitures",
            "Total sales change",
        ),
    ),
    (
        (),
        ("acquisition", "acquisitions", "acquired"),
        (
            "acquisition",
            "acquisitions",
            "completed the acquisition",
            "business combinations",
            "purchase price",
        ),
    ),
    (
        (),
        ("debt securities", "registered", "trading symbol"),
        (
            "Title of each class",
            "Trading Symbol",
            "Name of each exchange",
            "New York Stock Exchange",
        ),
    ),
    (
        (),
        ("dividend",),
        (
            "dividend",
            "dividends paid",
            "consecutive year",
            "dividend increases",
        ),
    ),
    (
        (),
        ("revenue", "net revenues", "net sales"),
        (
            "Consolidated Statement of Income",
            "Consolidated Statements of Operations",
            "Net revenues",
            "Net sales",
        ),
    ),
)


def messages_share_retrieval_cache_key(cached_message: str, message: str) -> bool:
    if message == cached_message:
        return True
    return str(message or "").startswith(
        str(cached_message or "").rstrip() + ANSWER_FORMAT_MARKER
    )


def retrieval_query(message: str, *, domain: str | None = None) -> str:
    question = str(message or "").split(ANSWER_FORMAT_MARKER, 1)[0]
    focus_terms = _retrieval_focus_terms(question, domain=domain)
    if not focus_terms:
        return question
    return f"{question}\n\nRetrieval focus: {'; '.join(focus_terms)}."


def _retrieval_focus_terms(question: str, *, domain: str | None) -> list[str]:
    if str(domain or "").strip().lower() == "finance":
        return _finance_retrieval_focus_terms(question)
    return _generic_retrieval_focus_terms(question)


def _generic_retrieval_focus_terms(question: str) -> list[str]:
    normalized = str(question or "").lower()
    if not _is_structured_calculation_question(normalized):
        return []
    return list(_GENERIC_STRUCTURED_CALCULATION_FOCUS)


def _is_structured_calculation_question(question: str) -> bool:
    return _has_any(question, _GENERIC_STRUCTURED_CALCULATION_TERMS) and _has_any(
        question,
        _GENERIC_STRUCTURED_CALCULATION_CONTEXT_TERMS,
    )


def _finance_retrieval_focus_terms(question: str) -> list[str]:
    normalized = str(question or "").lower()
    terms: list[str] = []
    for required_terms, alternative_terms, focus_terms in _FINANCE_FOCUS_RULES:
        if _matches_focus_rule(normalized, required_terms, alternative_terms):
            _extend_unique(terms, list(focus_terms))
    return terms


def _matches_focus_rule(
    value: str,
    required_terms: tuple[str, ...],
    alternative_terms: tuple[str, ...],
) -> bool:
    return all(term in value for term in required_terms) and _has_any(
        value,
        alternative_terms,
    )


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _extend_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)
