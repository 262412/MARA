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
) -> FinanceCalculationAudit:
    operands: list[CalculationOperand] = []
    used_evidence_ids: set[str] = set()
    for name, value in inputs.items():
        operand = _operand_from_input(
            name,
            value,
            question=question,
            evidence_items=evidence_items,
            excluded_evidence_ids=used_evidence_ids,
        )
        operands.append(operand)
        if operand.evidence_id and _atomic_evidence_id(
            operand.evidence_id, evidence_items
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
    evidence_items: list[dict[str, Any]],
    excluded_evidence_ids: set[str],
) -> CalculationOperand:
    decimal_value = Decimal(str(value))
    period = _operand_period(name, question)
    item = _matching_item(
        decimal_value,
        period,
        evidence_items,
        excluded_evidence_ids=excluded_evidence_ids,
    )
    text = _item_text(item) if item is not None else ""
    return CalculationOperand(
        operand_id=name,
        evidence_id=_item_id(item),
        value=decimal_value,
        unit=_item_dimension(item, "unit"),
        scale=_item_dimension(item, "scale") or _scale(text),
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
    if question_type == "inventory_turnover_average":
        return _inventory_turnover_average_steps(input_ids)
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


def _matching_item(
    value: Decimal,
    period: str,
    evidence_items: list[dict[str, Any]],
    *,
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
        if period_matches:
            matches = period_matches
    return matches[0] if matches else None


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
    if name == "value" and len(years) == 1:
        return years[0]
    return ""


def _shared_scale(operands: tuple[CalculationOperand, ...]) -> str:
    values = {operand.scale for operand in operands if operand.scale}
    return values.pop() if len(values) == 1 else ""


def _requested_scale(question: str) -> str:
    lowered = str(question or "").lower()
    for scale in ("billion", "million", "thousand"):
        if re.search(rf"\b{scale}s?\b", lowered):
            return scale
    return ""


def _scale(text: str) -> str:
    lowered = text.lower()
    for scale in ("billion", "million", "thousand"):
        if scale in lowered:
            return scale
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
