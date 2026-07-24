from __future__ import annotations

import re
from typing import Any


def metric_labels_for_question(lowered_question: str) -> tuple[str, ...]:
    metric_aliases = (
        ("adjusted_ebitda", ("adjusted ebitda", "adj. ebitda", "adj ebitda")),
        ("operating_income", ("operating income", "operating profit")),
        ("revenue", ("net sales", "net revenue", "net revenues", "revenue")),
        ("gross_profit", ("gross profit",)),
        ("total_assets", ("total assets",)),
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
    values: dict[str, float] = {}
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
        for match in re.finditer(label_first, text, flags=re.IGNORECASE):
            value = parse_amount(match.group(1))
            year = match.group(2)
            if value is not None and year not in values:
                values[year] = value
        for match in re.finditer(year_first, text, flags=re.IGNORECASE):
            year = match.group(1)
            value = parse_amount(match.group(2))
            if value is not None and year not in values:
                values[year] = value
    return values


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


def amount_after(text: str, labels: tuple[str, ...]) -> float | None:
    best: tuple[int, float] | None = None
    for label in labels:
        pattern = (
            rf"{re.escape(label)}[^\n\r\d(+-]{{0,80}}"
            rf"([(+\-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
        )
        for match in re.finditer(pattern, str(text or ""), flags=re.IGNORECASE):
            value = parse_amount(match.group(1))
            if value is None:
                continue
            candidate = (match.start(), value)
            if best is None or candidate[0] < best[0]:
                best = candidate
    return None if best is None else best[1]


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
        return format_currency_with_unit(value, amount_unit(text))
    if question_type in {
        "capital_expenditure",
        "dividend",
        "net_sales",
        "operating_income",
        "property_plant_equipment",
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
