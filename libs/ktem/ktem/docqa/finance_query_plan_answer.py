from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .calculation_evidence_identity import (
    calculation_evidence_items,
    calculation_evidence_lookup,
)
from .evidence_identity import identity_of
from .finance_calculation_contract import finance_calculation_authoritative
from .query_evidence_binding import bind_evidence_slots_monotonic
from .query_evidence_constraints import executable_operand_evidence
from .query_plan_schema import plan_from_payload


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
    authoritative_query_plan: dict[str, Any] = field(default_factory=dict)
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
    query_plan = _calculation_query_plan(query_plan)
    if not finance_calculation_authoritative(query_plan):
        return None
    constraints = dict(query_plan.get("constraints") or {})
    plan = plan_from_payload(
        prompt,
        answer_type=str(query_plan.get("answer_type") or "numeric"),
        verification_domain=str(constraints.get("verification_domain") or "finance"),
        payload=query_plan,
    )
    bound, binding_trace = bind_evidence_slots_monotonic(
        plan,
        calculation_evidence_items(evidence_items),
    )
    payload = bound.as_dict()
    payload["binding_trace"] = binding_trace
    return payload


def answer_from_query_plan(
    prompt: str,
    evidence_items: list[dict[str, Any]],
    *,
    query_plan: dict[str, Any] | None,
) -> FinanceNumericAnswer | None:
    if not isinstance(query_plan, dict):
        return None
    query_plan = _calculation_query_plan(query_plan)
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
        or len(list(slot.get("evidence_ids") or []))
        < max(1, int(slot.get("cardinality") or 1))
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
        and str(slot.get("slot_id") or "").startswith("operand:")
        and (
            str(slot.get("role") or "") == "operand"
            or bool(slot.get("required_for_execution"))
        )
    ]


def _resolved_operands(
    slots: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], Decimal]] | None:
    lookup = calculation_evidence_lookup(evidence_items)
    bound: list[tuple[dict[str, Any], Decimal]] = []
    for slot in slots:
        cardinality = max(1, int(slot.get("cardinality") or 1))
        items: dict[str, dict[str, Any]] = {}
        for evidence_id in slot.get("evidence_ids") or []:
            item = lookup.get(str(evidence_id))
            if item is not None:
                items.setdefault(identity_of(item).key, item)
        if len(items) < cardinality:
            return None
        for item in list(items.values())[:cardinality]:
            if not executable_operand_evidence(item):
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
    if formula_id == "inventory_turnover_average":
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="inventory_turnover_average",
            inputs=inputs,
            formula="cost_of_goods_sold / average(inventory_years)",
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
        and metrics == {"operating cash flow", "capital expenditure"}
        and ("free cash flow" in lowered or "fcf" in lowered)
    ):
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="free_cash_flow",
            inputs={_slot_operand_id(slot): float(value) for slot, value in bound},
            formula="operating_cash_flow - capital_expenditure",
        )
    if (
        len(bound) >= 2
        and metrics == {"revolving credit capacity"}
        and "total" in lowered
    ):
        input_id = str(bound[0][0].get("metric") or "").replace(" ", "_")
        inputs = {
            f"{input_id}_{index}": float(value)
            for index, (_slot, value) in enumerate(bound, start=1)
        }
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="revolving_credit_capacity",
            inputs=inputs,
            formula=" + ".join(inputs),
        )
    if (
        len(bound) == 2
        and len(metrics) == 1
        and any(phrase in lowered for phrase in ("drop", "decrease", "decline"))
    ):
        return FinanceNumericAnswer(
            answer="",
            confidence=0.95,
            question_type="percentage_decrease",
            inputs={_slot_operand_id(slot): float(value) for slot, value in bound},
            formula="(prior - current) / abs(prior) * 100",
        )
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
            inputs={_slot_operand_id(slot): float(value) for slot, value in bound},
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


def synchronize_authoritative_query_plan(
    query_plan: dict[str, Any] | None,
    calculation_plan: dict[str, Any],
    calculation_verification: dict[str, Any],
) -> dict[str, Any]:
    if not calculation_verification.get("valid"):
        return _calculation_query_plan(query_plan or {})
    authoritative = _reconciled_query_plan(
        query_plan,
        calculation_plan,
        state_authority="verified_calculation_plan",
    )
    if not authoritative:
        return authoritative
    authoritative["verified_required_slot_ids"] = list(
        calculation_verification.get("verified_required_slot_ids") or []
    )
    return authoritative


def reconcile_provisional_query_plan(
    query_plan: dict[str, Any] | None,
    calculation_plan: dict[str, Any],
) -> dict[str, Any]:
    return _reconciled_query_plan(
        query_plan,
        calculation_plan,
        state_authority="provisional_calculation_plan",
    )


def _reconciled_query_plan(
    query_plan: dict[str, Any] | None,
    calculation_plan: dict[str, Any],
    *,
    state_authority: str,
) -> dict[str, Any]:
    authoritative = _calculation_query_plan(query_plan or {})
    if not authoritative:
        return authoritative
    operands: dict[str, list[dict[str, Any]]] = {}
    for raw_operand in calculation_plan.get("operands") or []:
        if not isinstance(raw_operand, dict):
            continue
        query_slot_id = str(raw_operand.get("query_slot_id") or "")
        if query_slot_id:
            operands.setdefault(query_slot_id, []).append(dict(raw_operand))
    operand_values = [
        operand
        for grouped_operands in operands.values()
        for operand in grouped_operands
    ]
    slots: list[dict[str, Any]] = []
    for raw_slot in authoritative.get("evidence_slots") or []:
        if not isinstance(raw_slot, dict):
            continue
        slot = dict(raw_slot)
        slot_id = str(slot.get("slot_id") or "")
        slot_operands = operands.get(slot_id)
        if slot_operands is not None:
            slot.update(_operand_slot_state(slot_operands))
        elif str(slot.get("role") or "") == "dimension":
            slot.update(_dimension_slot_state(slot_id, operand_values))
        slots.append(slot)
    existing_slot_ids = {str(slot.get("slot_id") or "") for slot in slots}
    scale_slot = _new_dimension_slot("scale", operand_values)
    if scale_slot is not None and "dimension:scale" not in existing_slot_ids:
        slots.append(scale_slot)
    authoritative["evidence_slots"] = slots
    authoritative["state_authority"] = state_authority
    return authoritative


def _calculation_query_plan(query_plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(query_plan, dict):
        return {}
    payload = dict(query_plan)
    slots: list[dict[str, Any]] = []
    for value in query_plan.get("evidence_slots") or []:
        if not isinstance(value, dict):
            continue
        slot = dict(value)
        if str(slot.get("slot_id") or "").startswith("operand:"):
            slot["role"] = "operand"
            slot["required_for_execution"] = True
        slots.append(slot)
    payload["evidence_slots"] = slots
    payload["constraints"] = dict(query_plan.get("constraints") or {})
    return payload


def _operand_slot_state(operands: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_ids = list(
        dict.fromkeys(
            str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
            for operand in operands
            if str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
        )
    )
    state = {
        "role": "operand",
        "required_for_execution": True,
        "status": "filled" if evidence_ids else "missing",
        "evidence_ids": evidence_ids,
    }
    for field_name in (
        "source_id",
        "unit",
        "scale",
        "currency",
        "period",
        "period_kind",
        "statement_kind",
        "financial_scope",
        "table_instance_id",
        "table_group_id",
        "dimension_binding_scope",
    ):
        values = list(
            dict.fromkeys(
                str(operand.get(field_name) or "")
                for operand in operands
                if str(operand.get(field_name) or "")
            )
        )
        if values:
            state[field_name] = values[-1]
    return state


def _dimension_slot_state(
    slot_id: str,
    operands: Any,
) -> dict[str, Any]:
    dimension = slot_id.rsplit(":", 1)[-1]
    evidence_field = f"{dimension}_evidence_identity"
    raw_evidence_field = f"{dimension}_evidence_id"
    values = [
        str(operand.get(dimension) or "")
        for operand in operands
        if str(operand.get(dimension) or "")
    ]
    evidence_ids = list(
        dict.fromkeys(
            str(operand.get(evidence_field) or operand.get(raw_evidence_field) or "")
            for operand in operands
            if str(operand.get(evidence_field) or operand.get(raw_evidence_field) or "")
        )
    )
    state: dict[str, Any] = {
        "status": "filled" if values and evidence_ids else "missing",
        "evidence_ids": evidence_ids,
    }
    if len(set(values)) == 1:
        state[dimension] = values[0]
    scopes = list(
        dict.fromkeys(
            str(operand.get("dimension_binding_scope") or "")
            for operand in operands
            if str(operand.get("dimension_binding_scope") or "")
        )
    )
    if len(scopes) == 1:
        state["dimension_binding_scope"] = scopes[0]
    state["applied_query_slot_ids"] = list(
        dict.fromkeys(
            str(operand.get("query_slot_id") or "")
            for operand in operands
            if str(operand.get("query_slot_id") or "")
        )
    )
    return state


def _new_dimension_slot(
    dimension: str,
    operands: Any,
) -> dict[str, Any] | None:
    operand_values = list(operands)
    state = _dimension_slot_state(f"dimension:{dimension}", operand_values)
    if not any(str(operand.get(dimension) or "") for operand in operand_values):
        return None
    return {
        "slot_id": f"dimension:{dimension}",
        "role": "dimension",
        "entity": "",
        "metric": "",
        "period": "",
        "period_kind": "",
        "unit": "",
        "scale": "",
        "statement_kind": "",
        "financial_scope": "",
        "modality": "auto",
        "required": True,
        "required_for_retrieval": False,
        "required_for_execution": True,
        "required_for_verification": True,
        "cardinality": 1,
        "operator_role": "",
        "query": "",
        "locator": None,
        **state,
    }


def _direct_question_type(metric: str) -> str | None:
    return {
        "adjusted ebitda": "adjusted_ebitda",
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
        "formula_inputs": [],
        "operands": [],
        "steps": [],
        "result_step_id": "",
        "answer_unit": "",
        "answer_scale": "",
    }
