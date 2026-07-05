from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .evidence_text import evidence_text


@dataclass(frozen=True)
class FinanceNumericAnswer:
    answer: str
    confidence: float
    question_type: str
    inputs: dict[str, float]
    formula: str

    def as_trace(self) -> dict[str, Any]:
        return asdict(self)


def finance_numeric_answer(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> FinanceNumericAnswer | None:
    question = str(prompt or "")
    lowered = question.lower()
    text = evidence_text(evidence_items)
    if not text.strip():
        return None

    if "quick ratio" in lowered:
        return _quick_ratio_answer(text)
    if "current ratio" in lowered:
        return _ratio_answer(
            text,
            question_type="current_ratio",
            numerator_labels=("total current assets", "current assets"),
            denominator_labels=("total current liabilities", "current liabilities"),
            formula="current_assets / current_liabilities",
        )
    if "working capital" in lowered:
        return _difference_answer(
            text,
            question_type="working_capital",
            left_labels=("total current assets", "current assets"),
            right_labels=("total current liabilities", "current liabilities"),
            formula="current_assets - current_liabilities",
            currency=True,
        )
    if "inventory turnover" in lowered:
        return _ratio_answer(
            text,
            question_type="inventory_turnover",
            numerator_labels=("cost of sales", "cost of goods sold", "cogs"),
            denominator_labels=("average inventories", "inventories", "inventory"),
            formula="cost_of_sales / inventories",
        )
    if "operating margin" in lowered:
        return _percentage_ratio_answer(
            text,
            question_type="operating_margin",
            numerator_labels=("operating income", "operating profit"),
            denominator_labels=("net sales", "net revenue", "net revenues", "revenue"),
            formula="operating_income / net_sales",
        )
    if "gross margin" in lowered:
        return _percentage_ratio_answer(
            text,
            question_type="gross_margin",
            numerator_labels=("gross profit", "gross margin"),
            denominator_labels=("net sales", "net revenue", "net revenues", "revenue"),
            formula="gross_profit / net_sales",
        )
    if "debt" in lowered and "equity" in lowered:
        return _ratio_answer(
            text,
            question_type="debt_to_equity",
            numerator_labels=("total debt", "long-term debt", "short-term debt"),
            denominator_labels=(
                "total shareholders' equity",
                "total stockholders' equity",
                "shareholders' equity",
                "stockholders' equity",
            ),
            formula="debt / equity",
        )
    if "percentage change" in lowered or "percent change" in lowered:
        return _period_change_answer(lowered, text, percentage=True)
    if "difference" in lowered or "change in" in lowered:
        return _period_change_answer(lowered, text, percentage=False)
    if _asks_for_direct_finance_value(lowered):
        return _direct_value_answer(lowered, text)
    return None


def _quick_ratio_answer(text: str) -> FinanceNumericAnswer | None:
    assets = _amount_after(text, ("total current assets", "current assets"))
    inventories = _amount_after(text, ("total inventories", "inventories", "inventory"))
    liabilities = _amount_after(
        text,
        ("total current liabilities", "current liabilities"),
    )
    if assets is None or inventories is None or liabilities in (None, 0):
        return None
    value = (assets - inventories) / liabilities
    return FinanceNumericAnswer(
        answer=_format_decimal(value),
        confidence=0.92,
        question_type="quick_ratio",
        inputs={
            "current_assets": assets,
            "inventories": inventories,
            "current_liabilities": float(liabilities),
        },
        formula="(current_assets - inventories) / current_liabilities",
    )


def _ratio_answer(
    text: str,
    *,
    question_type: str,
    numerator_labels: tuple[str, ...],
    denominator_labels: tuple[str, ...],
    formula: str,
) -> FinanceNumericAnswer | None:
    numerator = _amount_after(text, numerator_labels)
    denominator = _amount_after(text, denominator_labels)
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / float(denominator)
    return FinanceNumericAnswer(
        answer=_format_decimal(value),
        confidence=0.86,
        question_type=question_type,
        inputs={"numerator": numerator, "denominator": float(denominator)},
        formula=formula,
    )


def _percentage_ratio_answer(
    text: str,
    *,
    question_type: str,
    numerator_labels: tuple[str, ...],
    denominator_labels: tuple[str, ...],
    formula: str,
) -> FinanceNumericAnswer | None:
    ratio = _ratio_answer(
        text,
        question_type=question_type,
        numerator_labels=numerator_labels,
        denominator_labels=denominator_labels,
        formula=formula,
    )
    if ratio is None:
        return None
    numerator = ratio.inputs["numerator"]
    denominator = ratio.inputs["denominator"]
    value = numerator / denominator * 100
    return FinanceNumericAnswer(
        answer=_format_percentage(value),
        confidence=0.86,
        question_type=question_type,
        inputs={"numerator": numerator, "denominator": denominator},
        formula=f"({formula}) * 100",
    )


def _difference_answer(
    text: str,
    *,
    question_type: str,
    left_labels: tuple[str, ...],
    right_labels: tuple[str, ...],
    formula: str,
    currency: bool,
) -> FinanceNumericAnswer | None:
    left = _amount_after(text, left_labels)
    right = _amount_after(text, right_labels)
    if left is None or right is None:
        return None
    value = left - right
    return FinanceNumericAnswer(
        answer=_format_currency(value) if currency else _format_number(value),
        confidence=0.88,
        question_type=question_type,
        inputs={"left": left, "right": right},
        formula=formula,
    )


def _direct_value_answer(lowered_question: str, text: str) -> FinanceNumericAnswer | None:
    candidates = [
        ("capital_expenditure", ("capital expenditures", "capital expenditure")),
        (
            "property_plant_equipment",
            ("property, plant and equipment", "property and equipment"),
        ),
        ("net_sales", ("net sales", "net revenue", "net revenues", "revenue")),
        ("operating_income", ("operating income", "operating profit")),
        ("total_assets", ("total assets",)),
        ("dividend", ("dividend", "dividends")),
    ]
    for question_type, labels in candidates:
        if not any(label in lowered_question for label in labels):
            continue
        value = _amount_after(text, labels)
        if value is None:
            continue
        return FinanceNumericAnswer(
            answer=_format_currency(value),
            confidence=0.78,
            question_type=question_type,
            inputs={"value": value},
            formula="direct_value",
        )
    return None


def _period_change_answer(
    lowered_question: str,
    text: str,
    *,
    percentage: bool,
) -> FinanceNumericAnswer | None:
    labels = _metric_labels_for_question(lowered_question)
    if not labels:
        return None
    values = _yearly_amounts(text, labels)
    years = _question_years(lowered_question)
    if len(years) >= 2 and years[0] in values and years[1] in values:
        prior_year, current_year = years[0], years[1]
    elif len(values) >= 2:
        prior_year, current_year = sorted(values)[:2]
    else:
        return None
    prior = values[prior_year]
    current = values[current_year]
    if percentage:
        if prior == 0:
            return None
        value = (current - prior) / abs(prior) * 100
        return FinanceNumericAnswer(
            answer=_format_percentage(value),
            confidence=0.82,
            question_type="percentage_change",
            inputs={"prior": prior, "current": current},
            formula="(current - prior) / abs(prior) * 100",
        )
    value = current - prior
    unit = _amount_unit(text)
    return FinanceNumericAnswer(
        answer=_format_currency_with_unit(value, unit),
        confidence=0.82,
        question_type="difference",
        inputs={"prior": prior, "current": current},
        formula="current - prior",
    )


def _metric_labels_for_question(lowered_question: str) -> tuple[str, ...]:
    metric_aliases = (
        ("operating_income", ("operating income", "operating profit")),
        ("revenue", ("net sales", "net revenue", "net revenues", "revenue")),
        ("gross_profit", ("gross profit",)),
        ("total_assets", ("total assets",)),
        ("capital_expenditure", ("capital expenditures", "capital expenditure")),
    )
    for _name, aliases in metric_aliases:
        if any(alias in lowered_question for alias in aliases):
            return aliases
    return ()


def _yearly_amounts(text: str, labels: tuple[str, ...]) -> dict[str, float]:
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
            value = _parse_amount(match.group(1))
            year = match.group(2)
            if value is not None and year not in values:
                values[year] = value
        for match in re.finditer(year_first, text, flags=re.IGNORECASE):
            year = match.group(1)
            value = _parse_amount(match.group(2))
            if value is not None and year not in values:
                values[year] = value
    return values


def _question_years(lowered_question: str) -> list[str]:
    return re.findall(r"\b(?:19|20)\d{2}\b", lowered_question)


def _asks_for_direct_finance_value(lowered_question: str) -> bool:
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


def _amount_after(text: str, labels: tuple[str, ...]) -> float | None:
    best: tuple[int, float] | None = None
    for label in labels:
        pattern = (
            rf"{re.escape(label)}[^\n\r\d(+-]{{0,80}}"
            rf"([(+\-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
        )
        for match in re.finditer(pattern, str(text or ""), flags=re.IGNORECASE):
            value = _parse_amount(match.group(1))
            if value is None:
                continue
            candidate = (match.start(), value)
            if best is None or candidate[0] < best[0]:
                best = candidate
    return None if best is None else best[1]


def _parse_amount(value: str) -> float | None:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("() ")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _format_decimal(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_percentage(value: float) -> str:
    return f"{value:.1f}%"


def _format_currency(value: float) -> str:
    rounded = round(value)
    prefix = "-$" if rounded < 0 else "$"
    return f"{prefix}{abs(rounded):,}"


def _format_number(value: float) -> str:
    if abs(value - round(value)) < 0.000001:
        return f"{int(round(value)):,}"
    return _format_decimal(value)


def _amount_unit(text: str) -> str:
    lowered = str(text or "").lower()
    if "billion" in lowered:
        return "billion"
    if "million" in lowered:
        return "million"
    return ""


def _format_currency_with_unit(value: float, unit: str) -> str:
    prefix = "-$" if value < 0 else "$"
    amount = abs(value)
    rendered = f"{prefix}{amount:,.1f}"
    return f"{rendered} {unit}".strip()
