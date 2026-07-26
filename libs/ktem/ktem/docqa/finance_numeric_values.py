from __future__ import annotations

import re
from typing import Any

DIRECT_VALUE_METRICS = (
    (
        "capital_expenditure",
        ("capital expenditures", "capital expenditure", "capital spending"),
    ),
    (
        "property_plant_equipment",
        (
            "property, plant and equipment",
            "property, plant, and equipment",
            "property and equipment",
        ),
    ),
    ("current_assets", ("total current assets", "current assets")),
    (
        "revolving_credit_capacity",
        (
            "revolving credit agreements",
            "revolving credit agreement",
            "credit facilities",
            "credit facility",
            "may borrow",
        ),
    ),
    ("net_sales", ("net sales", "net revenue", "net revenues", "revenue")),
    ("operating_income", ("operating income", "operating profit")),
    ("total_assets", ("total assets",)),
    ("dividend", ("dividend", "dividends")),
)


def metric_labels_for_question(lowered_question: str) -> tuple[str, ...]:
    if "total current assets" in lowered_question:
        return ("total current assets",)
    if re.search(
        r"\bnet\s+property,\s*plant(?:,\s*and| and)\s+equipment\b",
        lowered_question,
    ):
        return (
            "net property, plant and equipment",
            "net property, plant, and equipment",
            "property, plant and equipment, net",
            "property, plant, and equipment, net",
            "property and equipment, net",
        )
    metric_aliases = (
        ("adjusted_ebitda", ("adjusted ebitda", "adj. ebitda", "adj ebitda")),
        ("operating_income", ("operating income", "operating profit")),
        ("revenue", ("net sales", "net revenue", "net revenues", "revenue")),
        ("gross_profit", ("gross profit",)),
        ("current_assets", ("total current assets", "current assets")),
        ("total_assets", ("total assets",)),
        (
            "property_plant_equipment",
            (
                "property, plant and equipment",
                "property, plant, and equipment",
                "property and equipment",
            ),
        ),
        (
            "revolving_credit_capacity",
            (
                "revolving credit agreements",
                "revolving credit agreement",
                "credit facilities",
                "credit facility",
            ),
        ),
        (
            "capital_expenditure",
            ("capital expenditures", "capital expenditure", "capital spending"),
        ),
        ("inventory", ("inventories", "inventory")),
        (
            "cash_and_cash_equivalents",
            ("cash and cash equivalents", "cash & cash equivalents"),
        ),
    )
    for _name, aliases in metric_aliases:
        if any(alias in lowered_question for alias in aliases):
            return aliases
    return ()


def yearly_amounts(text: str, labels: tuple[str, ...]) -> dict[str, float]:
    from .financial_table import financial_table_yearly_amounts

    structured = financial_table_yearly_amounts(text, labels)
    candidates: dict[str, tuple[int, int, float]] = {}
    for clause in _yearly_fact_clauses(text):
        _collect_yearly_candidates(clause, labels, candidates)
    if not candidates:
        _collect_yearly_candidates(text, labels, candidates)
    narrative = {year: candidate[2] for year, candidate in candidates.items()}
    return {**narrative, **structured}


def _yearly_fact_clauses(text: str) -> list[str]:
    return [
        clause
        for clause in re.split(
            r"(?:[\n\r;]+|(?<=[A-Za-z0-9)%])\.\s+(?=[A-Z]))",
            str(text or ""),
        )
        if clause.strip()
    ]


def _collect_yearly_candidates(
    text: str,
    labels: tuple[str, ...],
    candidates: dict[str, tuple[int, int, float]],
) -> None:
    for label in labels:
        label_pattern = re.escape(label)
        label_first = (
            rf"{label_pattern}[^\n\r]{{0,140}}?"
            rf"([(+\-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
            rf"[^\n\r]{{0,80}}?\b((?:19|20)\d{{2}})\b"
        )
        year_first = (
            rf"\b((?:19|20)\d{{2}})\b[^\n\r]{{0,120}}?"
            rf"{label_pattern}[^\n\r]{{0,140}}?"
            rf"([(+\-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
        )
        for match in re.finditer(year_first, text, flags=re.IGNORECASE):
            year = match.group(1)
            value = parse_amount(match.group(2))
            _record_yearly_candidate(candidates, year, value, match)
        for match in re.finditer(label_first, text, flags=re.IGNORECASE):
            value = parse_amount(match.group(1))
            year = match.group(2)
            _record_yearly_candidate(candidates, year, value, match)


def _record_yearly_candidate(
    candidates: dict[str, tuple[int, int, float]],
    year: str,
    value: float | None,
    match: re.Match[str],
) -> None:
    if value is None:
        return
    candidate = (match.end() - match.start(), match.start(), value)
    if year not in candidates or candidate[:2] < candidates[year][:2]:
        candidates[year] = candidate


def question_years(lowered_question: str) -> list[str]:
    years = list(
        dict.fromkeys(
            re.findall(
                r"\b(?:fy\s*)?((?:19|20)\d{2})\b",
                lowered_question,
                flags=re.IGNORECASE,
            )
        )
    )
    if len(years) != 2 or not re.search(
        r"\b(?:from|between)\b.*\b(?:and|through|to)\b",
        lowered_question,
        flags=re.IGNORECASE,
    ):
        return years
    start, end = (int(value) for value in years)
    if start >= end or end - start > 10:
        return years
    return [str(year) for year in range(start, end + 1)]


def target_year(question: str, years: list[str]) -> str:
    match = re.search(
        r"\b(?:as\s+of|during|for|in)\s+(?:fy\s*)?((?:19|20)\d{2})\b",
        question,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match is not None else years[-1]


def asks_for_direct_finance_value(lowered_question: str) -> bool:
    return any(
        term in lowered_question
        for term in (
            "capital expenditure",
            "capex",
            "dividend",
            "net sales",
            "net revenue",
            "operating income",
            "operating profit",
            "property, plant and equipment",
            "property, plant, and equipment",
            "property and equipment",
            "total current assets",
            "current assets",
            "revolving credit agreement",
            "revolving credit agreements",
            "credit facility",
            "credit facilities",
            "may borrow",
            "total assets",
        )
    )


def asks_for_causal_explanation(lowered_question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:what\s+drove|why|causes?|caused|drivers?|factors?|reasons?)\b",
            lowered_question,
        )
    )


def amount_after(
    text: str,
    labels: tuple[str, ...],
    *,
    excluded_values: tuple[float, ...] = (),
) -> float | None:
    best: tuple[int, int, float] | None = None
    excluded = set(excluded_values)
    for label in labels:
        for label_match in re.finditer(
            re.escape(label),
            str(text or ""),
            flags=re.IGNORECASE,
        ):
            window = str(text or "")[label_match.end() : label_match.end() + 100]
            for amount_match in re.finditer(
                r"[(-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?",
                window,
            ):
                raw_value = amount_match.group(0)
                value = parse_amount(raw_value)
                if value is None or value in excluded:
                    continue
                dimensioned = int(
                    "$" in raw_value
                    or "," in raw_value
                    or bool(
                        re.match(
                            r"\s*(?:thousand|million|billion)s?\b",
                            window[amount_match.end() :],
                            flags=re.IGNORECASE,
                        )
                    )
                )
                candidate = (
                    -dimensioned,
                    label_match.start() + amount_match.start(),
                    value,
                )
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
    return None if best is None else best[2]


def period_amount(
    text: str,
    labels: tuple[str, ...],
    lowered_question: str,
) -> float | None:
    years = question_years(lowered_question)
    period = target_year(lowered_question, years) if years else ""
    value = yearly_amounts(text, labels).get(period)
    return value if value is not None else amount_after(text, labels)


def free_cash_flow_inputs(
    lowered_question: str,
    text: str,
) -> tuple[float, float] | None:
    operating_cash_flow = period_amount(
        text,
        (
            "net cash provided by operating activities",
            "cash provided by operating activities",
            "operating cash flow",
            "cash from operations",
        ),
        lowered_question,
    )
    capital_expenditure = period_amount(
        text,
        ("capital expenditures", "capital expenditure", "capital spending"),
        lowered_question,
    )
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    return operating_cash_flow, capital_expenditure


def revolving_credit_capacities(text: str) -> list[float]:
    capacities: list[float] = []
    pattern = (
        r"\b(?:borrow|borrowing)[^.:\n]{0,80}?\bup\s+to\s+"
        r"(\$?\s*\d[\d,]*(?:\.\d+)?)"
    )
    for match in re.finditer(pattern, str(text or ""), flags=re.IGNORECASE):
        value = parse_amount(match.group(1))
        if value is not None:
            capacities.append(value)
    return capacities


def direct_value_inputs(
    lowered_question: str,
    text: str,
) -> tuple[str, float, dict[str, float], str, float] | None:
    for question_type, labels in DIRECT_VALUE_METRICS:
        if not any(label in lowered_question for label in labels):
            continue
        labels = _qualified_direct_value_labels(
            question_type,
            labels,
            lowered_question,
        )
        years = question_years(lowered_question)
        if question_type == "revolving_credit_capacity" and "total" in (
            lowered_question
        ):
            capacities = revolving_credit_capacities(text)
            if len(capacities) >= 2:
                inputs = {
                    f"revolving_credit_capacity_{index}": value
                    for index, value in enumerate(capacities, start=1)
                }
                return (
                    question_type,
                    sum(capacities),
                    inputs,
                    " + ".join(inputs),
                    0.9,
                )
        values_by_year = yearly_amounts(text, labels)
        requested_year = target_year(lowered_question, years) if years else ""
        value = values_by_year.get(requested_year)
        if value is None:
            value = amount_after(
                text,
                labels,
                excluded_values=tuple(float(year) for year in years),
            )
        if value is not None:
            return question_type, value, {"value": value}, "direct_value", 0.78
    return None


def _qualified_direct_value_labels(
    question_type: str,
    labels: tuple[str, ...],
    question: str,
) -> tuple[str, ...]:
    if question_type == "current_assets" and "total current assets" in question:
        return ("total current assets",)
    if question_type == "property_plant_equipment" and re.search(
        r"\bnet\s+property\b",
        question,
    ):
        return (
            "net property, plant and equipment",
            "net property, plant, and equipment",
            "property, plant and equipment, net",
            "property, plant, and equipment, net",
            "property and equipment, net",
        )
    return labels


def parse_amount(value: str) -> float | None:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("() ")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return -parsed if negative else parsed


def format_decimal(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_percentage(value: float) -> str:
    return f"{value:.1f}%"


def format_currency(value: float) -> str:
    rounded = round(value)
    prefix = "-$" if rounded < 0 else "$"
    return f"{prefix}{abs(rounded):,}"


def format_number(value: float) -> str:
    if abs(value - round(value)) < 0.000001:
        return f"{int(round(value)):,}"
    return format_decimal(value)


def amount_unit(text: str) -> str:
    lowered = str(text or "").lower()
    if "billion" in lowered:
        return "billion"
    if "million" in lowered:
        return "million"
    return ""


def format_currency_with_unit(value: float, unit: str) -> str:
    prefix = "-$" if value < 0 else "$"
    amount = abs(value)
    rendered = f"{prefix}{amount:,.1f}"
    return f"{rendered} {unit}".strip()


def render_execution_answer(
    template: Any,
    value: Any,
    text: str,
    *,
    answer_scale: str = "",
) -> str:
    if value is None:
        return ""
    question_type = template.question_type
    if question_type in {
        "current_ratio",
        "debt_to_equity",
        "inventory_turnover",
        "inventory_turnover_average",
        "quick_ratio",
    }:
        return format_decimal(value)
    if question_type in {
        "gross_margin",
        "multi_period_ratio_average",
        "multi_period_percentage_average",
        "operating_margin",
        "percentage_change",
    }:
        return format_percentage(value)
    if question_type in {
        "difference",
        "free_cash_flow",
        "free_cash_flow_negative_capex",
        "multi_period_average",
        "working_capital",
    }:
        return format_currency_with_unit(value, answer_scale or amount_unit(text))
    if question_type in {
        "capital_expenditure",
        "dividend",
        "net_sales",
        "operating_income",
        "property_plant_equipment",
        "current_assets",
        "revolving_credit_capacity",
        "total_assets",
    }:
        if question_type == "capital_expenditure":
            value = abs(value)
        return _format_precise_currency(value, answer_scale)
    return template.answer


def _format_precise_currency(value: Any, unit: str) -> str:
    numeric = float(value)
    prefix = "-$" if numeric < 0 else "$"
    rendered = f"{abs(numeric):,.3f}".rstrip("0").rstrip(".")
    return f"{prefix}{rendered} {unit}".strip()
