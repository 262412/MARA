from __future__ import annotations

from typing import Any

from .metrics import numeric_tolerance_score

FINANCE_VIOLATION_KEYS = (
    "execution_slot_atomicity_violation_count",
    "parent_table_false_fill_count",
    "header_as_value_violation_count",
    "source_page_cross_join_count",
    "dimension_binding_violation_count",
    "dimension_scope_violation_count",
    "query_plan_calculation_plan_state_mismatch_count",
)
FINANCE_DIAGNOSTIC_KEYS = ("verified_execution_gold_discrepancy_count",)


def unique_finance_violation_summary(
    predictions: list[dict[str, Any]],
    metrics: list[dict[str, float | None]],
) -> dict[str, int]:
    summary = {
        f"{key.removesuffix('_count')}_unique_example_count": (
            _unique_violation_count(predictions, metrics, (key,))
        )
        for key in FINANCE_VIOLATION_KEYS
    }
    summary["finance_contract_violation_route_count"] = sum(
        any(float(metric.get(key) or 0.0) > 0 for key in FINANCE_VIOLATION_KEYS)
        for metric in metrics
    )
    summary[
        "finance_contract_violation_unique_example_count"
    ] = _unique_violation_count(predictions, metrics, FINANCE_VIOLATION_KEYS)
    for key in FINANCE_DIAGNOSTIC_KEYS:
        summary[
            f"{key.removesuffix('_count')}_unique_example_count"
        ] = _unique_violation_count(predictions, metrics, (key,))
    return summary


def query_plan_calculation_plan_state_mismatch(
    metadata: dict[str, Any],
) -> bool:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return False
    verification = trace.get("calculation_verification")
    execution = trace.get("calculation_execution")
    if (
        not isinstance(verification, dict)
        or not verification.get("valid")
        or not isinstance(execution, dict)
        or execution.get("status") != "ok"
    ):
        return False
    query_plan = metadata.get("query_plan")
    calculation_plan = trace.get("calculation_plan")
    if not isinstance(query_plan, dict) or not isinstance(calculation_plan, dict):
        return True
    if query_plan.get("state_authority") != "verified_calculation_plan":
        return True
    slots = {
        str(slot.get("slot_id") or ""): slot
        for slot in query_plan.get("evidence_slots") or []
        if isinstance(slot, dict) and str(slot.get("slot_id") or "")
    }
    operands = [
        operand
        for operand in calculation_plan.get("operands") or []
        if isinstance(operand, dict)
    ]
    operands_by_slot = {
        str(operand.get("query_slot_id") or ""): operand
        for operand in operands
        if str(operand.get("query_slot_id") or "")
    }
    verified_slot_ids = {
        str(value).strip()
        for value in verification.get("verified_required_slot_ids") or []
        if str(value or "").strip()
    }
    if any(
        slot_id not in operands_by_slot
        for slot_id in verified_slot_ids
        if not _is_execution_dimension_slot(slots.get(slot_id), slot_id)
    ):
        return True
    if any(
        slots.get(slot_id) is None
        or not _operand_state_matches(slots[slot_id], operand)
        for slot_id, operand in operands_by_slot.items()
    ):
        return True
    return any(
        not _dimension_state_matches(slots, operands, dimension)
        for dimension in ("scale", "unit", "currency")
    )


def _is_execution_dimension_slot(
    slot: dict[str, Any] | None,
    slot_id: str,
) -> bool:
    return bool(
        slot
        and str(slot.get("role") or "") == "dimension"
        and slot_id.rsplit(":", 1)[-1] in {"scale", "unit", "currency"}
    )


def verified_execution_gold_discrepancy(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return False
    verification = trace.get("calculation_verification")
    execution = trace.get("calculation_execution")
    if (
        not isinstance(verification, dict)
        or not verification.get("valid")
        or not isinstance(execution, dict)
        or execution.get("status") != "ok"
    ):
        return False
    predicted = str(
        prediction.get("answer_for_scoring")
        or prediction.get("predicted_answer")
        or trace.get("answer")
        or ""
    )
    executed = str(execution.get("value") or "")
    gold_answers = [str(value) for value in prediction.get("gold_answers") or []]
    return bool(
        predicted
        and executed
        and gold_answers
        and numeric_tolerance_score(predicted, [executed]) > 0
        and numeric_tolerance_score(predicted, gold_answers) == 0
    )


def _unique_violation_count(
    predictions: list[dict[str, Any]],
    metrics: list[dict[str, float | None]],
    keys: tuple[str, ...],
) -> int:
    identities = {
        str(
            prediction.get("example_id")
            or prediction.get("question_id")
            or f"route-record:{index}"
        )
        for index, (prediction, metric) in enumerate(zip(predictions, metrics))
        if any(float(metric.get(key) or 0.0) > 0 for key in keys)
    }
    return len(identities)


def _operand_state_matches(
    slot: dict[str, Any],
    operand: dict[str, Any],
) -> bool:
    evidence_id = str(
        operand.get("evidence_identity") or operand.get("evidence_id") or ""
    )
    if (
        str(slot.get("status") or "missing") != "filled"
        or not evidence_id
        or evidence_id not in set(slot.get("evidence_ids") or [])
    ):
        return False
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
    ):
        value = operand.get(field_name)
        if value not in (None, "") and slot.get(field_name) != value:
            return False
    return True


def _dimension_state_matches(
    slots: dict[str, dict[str, Any]],
    operands: list[dict[str, Any]],
    dimension: str,
) -> bool:
    evidence_ids = {
        str(
            operand.get(f"{dimension}_evidence_identity")
            or operand.get(f"{dimension}_evidence_id")
            or ""
        )
        for operand in operands
    }
    evidence_ids.discard("")
    if not evidence_ids:
        return True
    slot = next(
        (
            value
            for slot_id, value in slots.items()
            if str(value.get("role") or "") == "dimension"
            and slot_id.rsplit(":", 1)[-1] == dimension
        ),
        None,
    )
    return bool(
        slot
        and str(slot.get("status") or "missing") == "filled"
        and evidence_ids <= set(slot.get("evidence_ids") or [])
    )
