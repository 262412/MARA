from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .evidence_text import evidence_text
from .finance_calculation_adapter import finance_calculation_audit
from .finance_numeric_values import amount_after as _amount_after
from .finance_numeric_values import amount_unit as _amount_unit
from .finance_numeric_values import (
    asks_for_causal_explanation as _asks_for_causal_explanation,
)
from .finance_numeric_values import (
    asks_for_direct_finance_value as _asks_for_direct_finance_value,
)
from .finance_numeric_values import direct_value_inputs as _direct_value_inputs
from .finance_numeric_values import format_currency as _format_currency
from .finance_numeric_values import (
    format_currency_with_unit as _format_currency_with_unit,
)
from .finance_numeric_values import format_decimal as _format_decimal
from .finance_numeric_values import format_number as _format_number
from .finance_numeric_values import format_percentage as _format_percentage
from .finance_numeric_values import (
    metric_labels_for_question as _metric_labels_for_question,
)
from .finance_numeric_values import question_years as _question_years
from .finance_numeric_values import render_execution_answer as _render_execution_answer
from .finance_numeric_values import target_year as _target_year
from .finance_numeric_values import yearly_amounts as _yearly_amounts


@dataclass(frozen=True)
class FinanceNumericAnswer:
    answer: str
    confidence: float
    question_type: str
    inputs: dict[str, float]
    formula: str
    calculation_plan: dict[str, Any] = field(default_factory=dict)
    calculation_verification: dict[str, Any] = field(default_factory=dict)
    calculation_execution: dict[str, Any] = field(default_factory=dict)
    attempt_status: str = "executed"

    def as_trace(self) -> dict[str, Any]:
        return asdict(self)


def finance_numeric_answer(
    prompt: str,
    evidence_items: list[dict[str, Any]],
    *,
    query_plan: dict[str, Any] | None = None,
) -> FinanceNumericAnswer | None:
    answer = _finance_numeric_answer_from_text(prompt, evidence_items)
    if answer is None:
        failure_reason = _numeric_attempt_failure_reason(prompt, evidence_items)
        return _failed_numeric_attempt(failure_reason) if failure_reason else None
    audit = finance_calculation_audit(
        prompt,
        evidence_items,
        question_type=answer.question_type,
        inputs=answer.inputs,
        query_plan=query_plan,
    )
    if not audit.verification.valid or audit.execution.status != "ok":
        return replace(
            answer,
            answer="",
            confidence=0.0,
            calculation_plan=audit.plan.as_dict(),
            calculation_verification=audit.verification.as_dict(),
            calculation_execution=audit.execution.as_dict(),
            attempt_status="verification_failed",
        )
    verified_answer = _render_execution_answer(
        answer,
        audit.execution.value,
        evidence_text(evidence_items),
        answer_scale=audit.plan.answer_scale,
    )
    return replace(
        answer,
        answer=verified_answer,
        calculation_plan=audit.plan.as_dict(),
        calculation_verification=audit.verification.as_dict(),
        calculation_execution=audit.execution.as_dict(),
    )


def _finance_numeric_answer_from_text(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> FinanceNumericAnswer | None:
    question = str(prompt or "")
    lowered = question.lower()
    if _asks_for_causal_explanation(lowered):
        return None
    text = evidence_text(evidence_items)
    if not text.strip():
        return None

    if "free cash flow" in lowered or re.search(r"\bfcf\b", lowered):
        return _free_cash_flow_answer(lowered, text)
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
        average_answer = _average_inventory_turnover_answer(lowered, text)
        if average_answer is not None:
            return average_answer
        return _ratio_answer(
            text,
            question_type="inventory_turnover",
            numerator_labels=("cost of sales", "cost of goods sold", "cogs"),
            denominator_labels=("average inventories", "inventories", "inventory"),
            formula="cost_of_sales / inventories",
        )
    margin_or_leverage = _margin_or_leverage_answer(lowered, text)
    if margin_or_leverage is not None:
        return margin_or_leverage
    if _is_multi_period_ratio_average(lowered):
        return _multi_period_ratio_average_answer(lowered, text)
    if "average" in lowered and len(_question_years(lowered)) >= 2:
        return _multi_period_average_answer(lowered, text)
    if "percentage change" in lowered or "percent change" in lowered:
        return _period_change_answer(lowered, text, percentage=True)
    if "difference" in lowered or "change in" in lowered:
        return _period_change_answer(lowered, text, percentage=False)
    if _asks_for_direct_finance_value(lowered):
        return _direct_value_answer(lowered, text)
    return None


def _margin_or_leverage_answer(
    lowered_question: str,
    text: str,
) -> FinanceNumericAnswer | None:
    if "operating margin" in lowered_question:
        return _percentage_ratio_answer(
            text,
            question_type="operating_margin",
            numerator_labels=("operating income", "operating profit"),
            denominator_labels=("net sales", "net revenue", "net revenues", "revenue"),
            formula="operating_income / net_sales",
        )
    if "gross margin" in lowered_question:
        return _percentage_ratio_answer(
            text,
            question_type="gross_margin",
            numerator_labels=("gross profit", "gross margin"),
            denominator_labels=("net sales", "net revenue", "net revenues", "revenue"),
            formula="gross_profit / net_sales",
        )
    if "debt" in lowered_question and "equity" in lowered_question:
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
    return None


def _failed_numeric_attempt(reason: str) -> FinanceNumericAnswer:
    return FinanceNumericAnswer(
        answer="",
        confidence=0.0,
        question_type="unplanned_numeric",
        inputs={},
        formula="",
        calculation_plan={
            "contract_id": "calculation_plan.v1",
            "operands": [],
            "steps": [],
            "result_step_id": "",
            "answer_unit": "",
            "answer_scale": "",
        },
        calculation_verification={
            "valid": False,
            "errors": [reason],
            "verified_operand_ids": [],
            "citation_ids": [],
        },
        calculation_execution={
            "status": "error",
            "value": None,
            "citation_ids": [],
            "step_values": {},
            "error": reason,
        },
        attempt_status=reason,
    )


def _numeric_attempt_failure_reason(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> str:
    lowered = str(prompt or "").lower()
    if _asks_for_causal_explanation(lowered) or not _has_numeric_intent(lowered):
        return ""
    if not evidence_text(evidence_items).strip():
        return "missing_evidence"
    if _has_supported_formula_intent(lowered):
        return "missing_operands"
    return "unsupported_formula"


def _has_numeric_intent(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:amount|average|calculate|calculation|change|difference|"
            r"margin|percent(?:age)?|ratio|rate|total|turnover|value)\b",
            question,
        )
        or "free cash flow" in question
    )


def _has_supported_formula_intent(question: str) -> bool:
    return any(
        term in question
        for term in (
            "capital expenditure",
            "capital spending",
            "current ratio",
            "debt to equity",
            "difference",
            "free cash flow",
            "gross margin",
            "inventory turnover",
            "operating margin",
            "percent change",
            "percentage change",
            "quick ratio",
            "working capital",
        )
    ) or ("average" in question and len(_question_years(question)) >= 2)


def _free_cash_flow_answer(
    lowered_question: str,
    text: str,
) -> FinanceNumericAnswer | None:
    operating_cash_flow = _amount_after(
        text,
        (
            "net cash provided by operating activities",
            "cash provided by operating activities",
            "operating cash flow",
            "cash from operations",
        ),
    )
    capital_expenditure = _amount_after(
        text,
        (
            "capital expenditures",
            "capital expenditure",
            "capital spending",
        ),
    )
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    signed_capex = capital_expenditure < 0
    value = (
        operating_cash_flow + capital_expenditure
        if signed_capex
        else operating_cash_flow - capital_expenditure
    )
    unit = _amount_unit(text)
    return FinanceNumericAnswer(
        answer=_format_currency_with_unit(value, unit),
        confidence=0.9,
        question_type=(
            "free_cash_flow_negative_capex" if signed_capex else "free_cash_flow"
        ),
        inputs={
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditure": capital_expenditure,
        },
        formula=(
            "operating_cash_flow + capital_spending"
            if signed_capex
            else "operating_cash_flow - capital_expenditure"
        ),
    )


def _multi_period_average_answer(
    lowered_question: str,
    text: str,
) -> FinanceNumericAnswer | None:
    labels = _metric_labels_for_question(lowered_question)
    if not labels:
        return None
    values = _yearly_amounts(text, labels)
    years = _question_years(lowered_question)
    selected = [(year, values[year]) for year in years if year in values]
    if len(selected) < 2:
        return None
    inputs = {f"value_{year}": value for year, value in selected}
    average = sum(inputs.values()) / len(inputs)
    percentage = "%" in text and any(
        term in lowered_question for term in ("margin", "percent", "percentage")
    )
    unit = _amount_unit(text)
    return FinanceNumericAnswer(
        answer=(
            _format_percentage(average)
            if percentage
            else _format_currency_with_unit(average, unit)
        ),
        confidence=0.88,
        question_type=(
            "multi_period_percentage_average" if percentage else "multi_period_average"
        ),
        inputs=inputs,
        formula="average(" + ", ".join(inputs) + ")",
    )


def _is_multi_period_ratio_average(question: str) -> bool:
    return (
        "average" in question
        and len(_question_years(question)) >= 2
        and bool(
            re.search(
                r"\bas\s+(?:a\s+)?(?:%|percent(?:age)?)\s+of\b",
                question,
            )
        )
    )


def _multi_period_ratio_average_answer(
    lowered_question: str,
    text: str,
) -> FinanceNumericAnswer | None:
    years = _question_years(lowered_question)
    cogs = _yearly_amounts(
        text,
        ("cost of goods sold", "cost of sales", "cogs"),
    )
    revenue = _yearly_amounts(
        text,
        ("net sales", "net revenue", "net revenues", "revenue"),
    )
    if any(year not in cogs or year not in revenue for year in years):
        return None
    inputs: dict[str, float] = {}
    percentages: list[float] = []
    for year in years:
        if revenue[year] == 0:
            return None
        inputs[f"cost_of_goods_sold_{year}"] = cogs[year]
        inputs[f"revenue_{year}"] = revenue[year]
        percentages.append(cogs[year] / revenue[year] * 100)
    average = sum(percentages) / len(percentages)
    return FinanceNumericAnswer(
        answer=_format_percentage(average),
        confidence=0.9,
        question_type="multi_period_ratio_average",
        inputs=inputs,
        formula="average(cost_of_goods_sold_year / revenue_year * 100)",
    )


def _average_inventory_turnover_answer(
    lowered_question: str,
    text: str,
) -> FinanceNumericAnswer | None:
    years = _question_years(lowered_question)
    if len(years) < 2 or "average" not in lowered_question:
        return None
    inventory_values = _yearly_amounts(text, ("inventories", "inventory"))
    cogs_values = _yearly_amounts(
        text,
        ("cost of goods sold", "cost of sales", "cogs"),
    )
    inventory_periods = [
        year for year in dict.fromkeys(years) if year in inventory_values
    ]
    target_year = _target_year(lowered_question, years)
    if len(inventory_periods) < 2 or target_year not in cogs_values:
        return None
    inventory_inputs = {
        f"inventory_{year}": inventory_values[year] for year in inventory_periods
    }
    average_inventory = sum(inventory_inputs.values()) / len(inventory_inputs)
    if average_inventory == 0:
        return None
    cogs = cogs_values[target_year]
    return FinanceNumericAnswer(
        answer=_format_decimal(cogs / average_inventory),
        confidence=0.9,
        question_type="inventory_turnover_average",
        inputs={"cost_of_goods_sold": cogs, **inventory_inputs},
        formula="cost_of_goods_sold / average(inventory periods)",
    )


def _quick_ratio_answer(text: str) -> FinanceNumericAnswer | None:
    assets = _amount_after(text, ("total current assets", "current assets"))
    inventories = _amount_after(text, ("total inventories", "inventories", "inventory"))
    liabilities = _amount_after(
        text,
        ("total current liabilities", "current liabilities"),
    )
    if assets is None or inventories is None or liabilities is None or liabilities == 0:
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
    if numerator is None or denominator is None or denominator == 0:
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


def _direct_value_answer(
    lowered_question: str, text: str
) -> FinanceNumericAnswer | None:
    parsed = _direct_value_inputs(lowered_question, text)
    if parsed is None:
        return None
    question_type, value, inputs, formula, confidence = parsed
    return FinanceNumericAnswer(
        answer=_format_currency(value),
        confidence=confidence,
        question_type=question_type,
        inputs=inputs,
        formula=formula,
    )


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
