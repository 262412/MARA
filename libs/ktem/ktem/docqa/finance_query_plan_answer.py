from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .calculation_evidence_identity import (
    calculation_evidence_items,
    calculation_evidence_lookup,
)
from .query_evidence_constraints import executable_operand_evidence
from .query_plan_schema import plan_from_payload
from .query_planning import bind_evidence_slots


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
        trace = asdict(self)
        trace["dimension_bindings"] = _dimension_bindings(self.calculation_plan)
        return trace


def bind_numeric_query_plan(
    prompt: str,
    evidence_items: list[dict[str, Any]],
    query_plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(query_plan, dict):
        return None
    slots = [
        slot
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
    ]
    execution_slots = [
        slot for slot in slots if bool(slot.get("required_for_execution"))
    ]
    if execution_slots and all(
        str(slot.get("status") or "") == "filled" and bool(slot.get("evidence_ids"))
        for slot in execution_slots
    ):
        return query_plan
    constraints = dict(query_plan.get("constraints") or {})
    plan = plan_from_payload(
        prompt,
        answer_type=str(query_plan.get("answer_type") or "numeric"),
        verification_domain=str(constraints.get("verification_domain") or "finance"),
        payload=query_plan,
    )
    return bind_evidence_slots(
        plan,
        calculation_evidence_items(evidence_items),
    ).as_dict()


def answer_from_query_plan(
    prompt: str,
    evidence_items: list[dict[str, Any]],
    *,
    query_plan: dict[str, Any] | None,
) -> FinanceNumericAnswer | None:
    if not isinstance(query_plan, dict):
        return None
    constraints = dict(query_plan.get("constraints") or {})
    if constraints.get("finance_formula_status") == "unsupported":
        return failed_numeric_attempt("unsupported_formula")
    slots = _execution_operand_slots(query_plan)
    if not slots:
        return None
    missing_slots = [
        slot
        for slot in slots
        if str(slot.get("status") or "missing") != "filled"
        or not list(slot.get("evidence_ids") or [])
    ]
    if missing_slots:
        return _failed_plan_attempt(missing_slots)
    bound = _resolved_operands(slots, evidence_items)
    if bound is None:
        return failed_numeric_attempt("missing_operands")
    formula_answer = _formula_answer(constraints, bound)
    if formula_answer is not None:
        return formula_answer
    return _generic_plan_answer(prompt, bound)


def failed_numeric_attempt(reason: str) -> FinanceNumericAnswer:
    return FinanceNumericAnswer(
        answer="",
        confidence=0.0,
        question_type="unplanned_numeric",
        inputs={},
        formula="",
        calculation_plan=_empty_calculation_plan(),
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


def _execution_operand_slots(
    query_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        dict(slot)
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and str(slot.get("role") or "") == "operand"
        and bool(slot.get("required_for_execution"))
    ]


def _resolved_operands(
    slots: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], Decimal]] | None:
    lookup = calculation_evidence_lookup(evidence_items)
    bound: list[tuple[dict[str, Any], Decimal]] = []
    for slot in slots:
        item = next(
            (
                lookup.get(str(evidence_id))
                for evidence_id in slot.get("evidence_ids") or []
                if lookup.get(str(evidence_id)) is not None
            ),
            None,
        )
        if item is None or not executable_operand_evidence(item):
            return None
        value = _structured_decimal(item.get("value"))
        if value is None:
            return None
        bound.append((slot, value))
    return bound


def _formula_answer(
    constraints: dict[str, Any],
    bound: list[tuple[dict[str, Any], Decimal]],
) -> FinanceNumericAnswer | None:
    formula = dict(constraints.get("finance_formula") or {})
    formula_id = str(formula.get("formula_id") or formula.get("name") or "")
    inputs = {_slot_operand_id(slot): float(value) for slot, value in bound}
    if formula_id == "fixed_asset_turnover":
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="fixed_asset_turnover",
            inputs=inputs,
            formula="net_sales_target / average(net_ppe_previous, net_ppe_target)",
        )
    if formula_id == "multi_period_percentage_of_average":
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="multi_period_ratio_average",
            inputs=inputs,
            formula="average(numerator_year / denominator_year * 100)",
        )
    return None


def _generic_plan_answer(
    prompt: str,
    bound: list[tuple[dict[str, Any], Decimal]],
) -> FinanceNumericAnswer | None:
    metrics = {str(slot.get("metric") or "") for slot, _value in bound}
    lowered = str(prompt or "").lower()
    if (
        len(bound) == 2
        and len(metrics) == 1
        and any(
            phrase in lowered
            for phrase in (
                "percentage change",
                "percent change",
                "year-over-year change",
            )
        )
    ):
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="percentage_change",
            inputs={"prior": float(bound[0][1]), "current": float(bound[1][1])},
            formula="(current - prior) / abs(prior) * 100",
        )
    if len(bound) != 1:
        return None
    slot, value = bound[0]
    question_type = _direct_question_type(str(slot.get("metric") or ""))
    if question_type is None:
        return None
    return FinanceNumericAnswer(
        answer="",
        confidence=0.95,
        question_type=question_type,
        inputs={_slot_operand_id(slot): float(value)},
        formula="direct_value",
    )


def _failed_plan_attempt(
    missing_slots: list[dict[str, Any]],
) -> FinanceNumericAnswer:
    errors = [f"required_slot_missing:{slot.get('slot_id')}" for slot in missing_slots]
    return FinanceNumericAnswer(
        answer="",
        confidence=0.0,
        question_type="unplanned_numeric",
        inputs={},
        formula="",
        calculation_plan=_empty_calculation_plan(),
        calculation_verification={
            "valid": False,
            "errors": errors,
            "verified_operand_ids": [],
            "citation_ids": [],
            "required_slot_ids": [
                str(slot.get("slot_id") or "") for slot in missing_slots
            ],
            "verified_required_slot_ids": [],
        },
        calculation_execution={
            "status": "error",
            "value": None,
            "citation_ids": [],
            "step_values": {},
            "error": "verification_failed",
        },
        attempt_status="verification_failed",
    )


def _dimension_bindings(
    calculation_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    bindings: dict[tuple[str, str, str], dict[str, Any]] = {}
    for operand in calculation_plan.get("operands") or []:
        if not isinstance(operand, dict):
            continue
        evidence_id = str(
            operand.get("scale_evidence_identity")
            or operand.get("scale_evidence_id")
            or ""
        ).strip()
        scale = str(operand.get("scale") or "").strip()
        if not evidence_id or not scale:
            continue
        scope = str(operand.get("dimension_binding_scope") or "").strip()
        key = (evidence_id, scale, scope)
        binding = bindings.setdefault(
            key,
            {
                "dimension_slot_id": "dimension:scale",
                "dimension_evidence_id": evidence_id,
                "detected_scale": scale,
                "applied_operand_ids": [],
                "binding_scope": scope,
            },
        )
        binding["applied_operand_ids"].append(str(operand.get("operand_id") or ""))
    return list(bindings.values())


def _direct_question_type(metric: str) -> str | None:
    return {
        "capital expenditure": "capital_expenditure",
        "current assets": "current_assets",
        "net property plant and equipment": "property_plant_equipment",
        "net sales": "net_sales",
        "operating income": "operating_income",
        "total assets": "total_assets",
    }.get(metric)


def _slot_operand_id(slot: dict[str, Any]) -> str:
    slot_id = str(slot.get("slot_id") or "").removeprefix("operand:")
    return slot_id.replace(":", "_")


def _structured_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _empty_calculation_plan() -> dict[str, Any]:
    return {
        "contract_id": "calculation_plan.v1",
        "operands": [],
        "steps": [],
        "result_step_id": "",
        "answer_unit": "",
        "answer_scale": "",
    }
