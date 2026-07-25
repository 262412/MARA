from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .calculation_plan import (
    CalculationExecution,
    CalculationOperand,
    CalculationPlan,
    CalculationStep,
    CalculationVerification,
    execute_calculation_plan,
    verify_calculation_plan,
)
from .finance_query_planning import FINANCE_METRIC_ALIASES


@dataclass(frozen=True)
class FinanceCalculationAudit:
    plan: CalculationPlan
    verification: CalculationVerification
    execution: CalculationExecution


def finance_calculation_audit(
    question: str,
    evidence_items: list[dict[str, Any]],
    *,
    question_type: str,
    inputs: dict[str, float],
    query_plan: dict[str, Any] | None = None,
) -> FinanceCalculationAudit:
    operands: list[CalculationOperand] = []
    used_evidence_ids: set[str] = set()
    for name, value in inputs.items():
        operand = _operand_from_input(
            name,
            value,
            question=question,
            question_type=question_type,
            evidence_items=evidence_items,
            excluded_evidence_ids=used_evidence_ids,
        )
        operands.append(operand)
        repeated_value = list(inputs.values()).count(value) > 1
        if (
            repeated_value
            and operand.evidence_id
            and not name.startswith("revolving_credit_capacity_")
            and _atomic_evidence_id(operand.evidence_id, evidence_items)
        ):
            used_evidence_ids.add(operand.evidence_id)
    operand_tuple = tuple(operands)
    steps, result_step_id, answer_unit = _steps(question_type, tuple(inputs))
    scale = _shared_scale(operand_tuple)
    scaled_result_types = {
        "capital_expenditure",
        "difference",
        "dividend",
        "free_cash_flow",
        "free_cash_flow_negative_capex",
        "multi_period_average",
        "net_sales",
        "operating_income",
        "property_plant_equipment",
        "current_assets",
        "revolving_credit_capacity",
        "total_assets",
        "working_capital",
    }
    requested_scale = _requested_scale(question)
    result_scale = requested_scale or scale
    plan = CalculationPlan(
        operands=operand_tuple,
        steps=steps,
        result_step_id=result_step_id,
        answer_unit=answer_unit,
        answer_scale=(
            result_scale if question_type in scaled_result_types or not steps else ""
        ),
    )
    verification = verify_calculation_plan(
        plan,
        evidence_items,
        question=question,
        required_slots=[
            dict(slot) for slot in (query_plan or {}).get("evidence_slots") or []
        ],
    )
    execution = (
        execute_calculation_plan(plan)
        if verification.valid
        else CalculationExecution(
            status="error",
            value=None,
            error="verification_failed",
        )
    )
    return FinanceCalculationAudit(plan, verification, execution)


def _operand_from_input(
    name: str,
    value: float,
    *,
    question: str,
    question_type: str,
    evidence_items: list[dict[str, Any]],
    excluded_evidence_ids: set[str],
) -> CalculationOperand:
    decimal_value = Decimal(str(value))
    period = _operand_period(name, question)
    if (
        period
        and _single_question_period(question) == period
        and not any(period in _item_text(item) for item in evidence_items)
    ):
        period = ""
    item = _matching_item(
        name,
        decimal_value,
        period,
        question=question,
        question_type=question_type,
        evidence_items=evidence_items,
        excluded_evidence_ids=excluded_evidence_ids,
    )
    text = _item_text(item) if item is not None else ""
    return CalculationOperand(
        operand_id=name,
        evidence_id=_item_id(item),
        value=decimal_value,
        unit=_item_dimension(item, "unit"),
        scale=_item_dimension(item, "scale")
        or _scale(text, aliases=_operand_aliases(name, question, question_type)),
        currency=(
            _item_dimension(item, "currency")
            or ("USD" if "$" in text or "usd" in text.lower() else "")
        ),
        period=period or _item_dimension(item, "period"),
        entity=_item_dimension(item, "entity"),
    )


def _steps(
    question_type: str,
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    if question_type == "quick_ratio":
        return _quick_ratio_steps()
    if question_type in {
        "current_ratio",
        "inventory_turnover",
        "debt_to_equity",
    }:
        return ((CalculationStep("result", "ratio", input_ids),), "result", "ratio")
    if question_type in {"operating_margin", "gross_margin"}:
        return _margin_steps(input_ids)
    if question_type == "percentage_change":
        return (
            (CalculationStep("result", "percent_change", ("prior", "current")),),
            "result",
            "percent",
        )
    if question_type in {
        "free_cash_flow",
        "free_cash_flow_negative_capex",
    }:
        return _free_cash_flow_steps(question_type)
    if question_type in {
        "multi_period_average",
        "multi_period_percentage_average",
    }:
        return (
            (CalculationStep("result", "average", input_ids),),
            "result",
            "percent" if question_type == "multi_period_percentage_average" else "",
        )
    if question_type == "multi_period_ratio_average":
        return _multi_period_ratio_average_steps(input_ids)
    if question_type == "inventory_turnover_average":
        return _inventory_turnover_average_steps(input_ids)
    if question_type == "revolving_credit_capacity" and len(input_ids) > 1:
        return (
            (CalculationStep("result", "add", input_ids),),
            "result",
            "",
        )
    if question_type in {"difference", "working_capital"}:
        names = (
            ("prior", "current") if question_type == "difference" else ("left", "right")
        )
        ordered = (names[1], names[0]) if question_type == "difference" else names
        return ((CalculationStep("result", "subtract", ordered),), "result", "")
    return (), input_ids[0], ""


def _quick_ratio_steps() -> tuple[tuple[CalculationStep, ...], str, str]:
    return (
        (
            CalculationStep(
                "liquid_assets",
                "subtract",
                ("current_assets", "inventories"),
            ),
            CalculationStep(
                "result",
                "ratio",
                ("liquid_assets", "current_liabilities"),
            ),
        ),
        "result",
        "ratio",
    )


def _margin_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    return (
        (
            CalculationStep("ratio", "ratio", input_ids),
            CalculationStep(
                "result",
                "multiply",
                ("ratio",),
                constant=Decimal("100"),
            ),
        ),
        "result",
        "percent",
    )


def _free_cash_flow_steps(
    question_type: str,
) -> tuple[tuple[CalculationStep, ...], str, str]:
    operator = "add" if question_type == "free_cash_flow_negative_capex" else "subtract"
    return (
        (
            CalculationStep(
                "result",
                operator,
                ("operating_cash_flow", "capital_expenditure"),
            ),
        ),
        "result",
        "",
    )


def _inventory_turnover_average_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    inventory_ids = tuple(
        input_id for input_id in input_ids if input_id.startswith("inventory_")
    )
    return (
        (
            CalculationStep(
                "average_inventory",
                "average",
                inventory_ids,
            ),
            CalculationStep(
                "result",
                "ratio",
                ("cost_of_goods_sold", "average_inventory"),
            ),
        ),
        "result",
        "ratio",
    )


def _multi_period_ratio_average_steps(
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    years = list(
        dict.fromkeys(
            match.group(0)
            for input_id in input_ids
            if (match := re.search(r"(?:19|20)\d{2}", input_id))
        )
    )
    steps: list[CalculationStep] = []
    percentage_ids: list[str] = []
    for year in years:
        numerator = next(
            input_id
            for input_id in input_ids
            if input_id.endswith(year) and input_id.startswith("cost_of_goods_sold")
        )
        denominator = next(
            input_id
            for input_id in input_ids
            if input_id.endswith(year) and input_id.startswith("revenue")
        )
        ratio_id = f"ratio_{year}"
        percentage_id = f"percentage_{year}"
        steps.extend(
            (
                CalculationStep(ratio_id, "ratio", (numerator, denominator)),
                CalculationStep(
                    percentage_id,
                    "multiply",
                    (ratio_id,),
                    constant=Decimal("100"),
                ),
            )
        )
        percentage_ids.append(percentage_id)
    steps.append(CalculationStep("result", "average", tuple(percentage_ids)))
    return tuple(steps), "result", "percent"


def _matching_item(
    name: str,
    value: Decimal,
    period: str,
    *,
    question: str,
    question_type: str,
    evidence_items: list[dict[str, Any]],
    excluded_evidence_ids: set[str],
) -> dict[str, Any] | None:
    matches = [
        item
        for item in evidence_items
        if value in _decimal_values(_item_text(item))
        and _item_id(item) not in excluded_evidence_ids
    ]
    if period:
        period_matches = [item for item in matches if period in _item_text(item)]
        if not period_matches:
            return None
        matches = period_matches
    aliases = _operand_aliases(name, question, question_type)
    ranked = sorted(
        enumerate(matches),
        key=lambda row: (
            -_metric_support(row[1], aliases),
            -bool(_item_dimension(row[1], "scale") or _scale(_item_text(row[1]))),
            row[0],
        ),
    )
    return ranked[0][1] if ranked else None


def _operand_aliases(
    name: str,
    question: str,
    question_type: str,
) -> tuple[str, ...]:
    if question_type == "working_capital":
        metric = "current assets" if name == "left" else "current liabilities"
        return FINANCE_METRIC_ALIASES[metric]
    formula_metrics = {
        "current_ratio": ("current assets", "current liabilities"),
        "debt_to_equity": ("total debt", "shareholders equity"),
        "gross_margin": ("gross profit", "net sales"),
        "operating_margin": ("operating income", "net sales"),
    }
    if question_type in formula_metrics and name in {"numerator", "denominator"}:
        metric = formula_metrics[question_type][name == "denominator"]
        return FINANCE_METRIC_ALIASES[metric]
    canonical = re.sub(r"_(?:19|20)\d{2}$", "", name).replace("_", " ")
    if canonical == "inventories":
        canonical = "inventory"
    aliases = FINANCE_METRIC_ALIASES.get(canonical)
    if aliases:
        return aliases
    from .finance_numeric_values import metric_labels_for_question

    return metric_labels_for_question(question.lower())


def _metric_support(item: dict[str, Any], aliases: tuple[str, ...]) -> int:
    lowered = _item_text(item).lower()
    return int(any(alias.lower() in lowered for alias in aliases))


def _operand_period(name: str, question: str) -> str:
    years = re.findall(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    name_period = re.search(r"(?:19|20)\d{2}", name)
    if name_period is not None:
        return name_period.group(0)
    if name == "prior" and years:
        return years[0]
    if name == "current" and len(years) >= 2:
        return years[1]
    if len(years) == 1:
        return years[0]
    return ""


def _single_question_period(question: str) -> str:
    years = list(
        dict.fromkeys(
            re.findall(
                r"\b(?:fy\s*)?((?:19|20)\d{2})\b",
                str(question or ""),
                flags=re.IGNORECASE,
            )
        )
    )
    return years[0] if len(years) == 1 else ""


def _shared_scale(operands: tuple[CalculationOperand, ...]) -> str:
    values = {operand.scale for operand in operands if operand.scale}
    return values.pop() if len(values) == 1 else ""


def _requested_scale(question: str) -> str:
    lowered = str(question or "").lower()
    for scale in ("billion", "million", "thousand"):
        if re.search(rf"\b{scale}s?\b", lowered):
            return scale
    return ""


def _scale(text: str, *, aliases: tuple[str, ...] = ()) -> str:
    lowered = text.lower()
    header = re.search(
        r"\(\s*in\s+(thousands?|millions?|billions?)\b",
        lowered,
    )
    if header is not None:
        return header.group(1).rstrip("s")
    for alias in aliases:
        match = re.search(
            rf"{re.escape(alias.lower())}.{{0,100}}?"
            r"(thousands?|millions?|billions?)\b",
            lowered,
        )
        if match is not None:
            return match.group(1).rstrip("s")
    return ""


def _item_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return str(
        item.get("element_id")
        or item.get("evidence_id")
        or item.get("canonical_id")
        or ""
    ).strip()


def _atomic_evidence_id(
    evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> bool:
    return any(
        _item_id(item) == evidence_id
        and bool(item.get("cell_id") or item.get("element_id"))
        for item in evidence_items
    )


def _item_text(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def _item_dimension(item: dict[str, Any] | None, field: str) -> str:
    if item is None:
        return ""
    metadata = dict(item.get("metadata") or {})
    return str(item.get(field) or metadata.get(field) or "").strip()


def _decimal_values(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    pattern = (
        r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|" r"\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
    )
    for raw in re.findall(pattern, text):
        normalized = raw.replace("$", "").replace(",", "").replace(" ", "")
        negative = "(" in normalized and normalized.endswith(")")
        try:
            parsed = Decimal(normalized.strip("()"))
        except InvalidOperation:
            continue
        values.append(-parsed if negative else parsed)
    return values
