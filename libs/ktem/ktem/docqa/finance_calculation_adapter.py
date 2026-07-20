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
    operands = tuple(
        _operand_from_input(
            name,
            value,
            question=question,
            evidence_items=evidence_items,
        )
        for name, value in inputs.items()
    )
    steps, result_step_id, answer_unit = _steps(question_type, tuple(inputs))
    scale = _shared_scale(operands)
    plan = CalculationPlan(
        operands=operands,
        steps=steps,
        result_step_id=result_step_id,
        answer_unit=answer_unit,
        answer_scale=(
            scale
            if question_type in {"difference", "working_capital"} or not steps
            else ""
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
) -> CalculationOperand:
    decimal_value = Decimal(str(value))
    period = _operand_period(name, question)
    item = _matching_item(decimal_value, period, evidence_items)
    text = _item_text(item) if item is not None else ""
    return CalculationOperand(
        operand_id=name,
        evidence_id=_item_id(item),
        value=decimal_value,
        scale=_scale(text),
        currency="USD" if "$" in text or "usd" in text.lower() else "",
        period=period,
    )


def _steps(
    question_type: str,
    input_ids: tuple[str, ...],
) -> tuple[tuple[CalculationStep, ...], str, str]:
    if question_type == "quick_ratio":
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
    if question_type in {
        "current_ratio",
        "inventory_turnover",
        "debt_to_equity",
    }:
        return ((CalculationStep("result", "ratio", input_ids),), "result", "ratio")
    if question_type in {"operating_margin", "gross_margin"}:
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
    if question_type == "percentage_change":
        return (
            (CalculationStep("result", "percent_change", ("prior", "current")),),
            "result",
            "percent",
        )
    if question_type in {"difference", "working_capital"}:
        names = (
            ("prior", "current") if question_type == "difference" else ("left", "right")
        )
        ordered = (names[1], names[0]) if question_type == "difference" else names
        return ((CalculationStep("result", "subtract", ordered),), "result", "")
    return (), input_ids[0], ""


def _matching_item(
    value: Decimal,
    period: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        item for item in evidence_items if value in _decimal_values(_item_text(item))
    ]
    if period:
        period_matches = [item for item in matches if period in _item_text(item)]
        if period_matches:
            matches = period_matches
    return matches[0] if matches else None


def _operand_period(name: str, question: str) -> str:
    years = re.findall(r"\b(?:19|20)\d{2}\b", str(question or ""))
    if name == "prior" and years:
        return years[0]
    if name == "current" and len(years) >= 2:
        return years[1]
    return ""


def _shared_scale(operands: tuple[CalculationOperand, ...]) -> str:
    values = {operand.scale for operand in operands if operand.scale}
    return values.pop() if len(values) == 1 else ""


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


def _item_text(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


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
