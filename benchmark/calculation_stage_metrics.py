from __future__ import annotations

import re
from typing import Any


def calculation_metrics(
    finance: dict[str, Any],
    *,
    applicable: bool,
    rendered_answer: str,
) -> dict[str, float | None]:
    plan = dict(finance.get("calculation_plan") or {})
    verification = dict(finance.get("calculation_verification") or {})
    execution = dict(finance.get("calculation_execution") or {})
    operands = _records(plan.get("operands"))
    steps = _records(plan.get("steps"))
    if not plan:
        return _empty_metrics(applicable)
    verified = set(verification.get("verified_operand_ids") or [])
    errors = [str(error) for error in verification.get("errors") or []]
    required_slots = list(verification.get("required_slot_ids") or [])
    verified_required = set(verification.get("verified_required_slot_ids") or [])
    operand_accuracy = (
        len(verified_required) / len(required_slots)
        if required_slots
        else len(verified) / len(operands)
        if operands
        else None
    )
    cell_errors = [
        error
        for error in errors
        if any(
            term in error
            for term in (
                "evidence_missing",
                "cell_mismatch",
                "value_mismatch",
                "period_mismatch",
            )
        )
    ]
    operator_errors = [
        error
        for error in errors
        if "operator" in error or "step_input" in error or "arity" in error
    ]
    unit_errors = [
        error
        for error in errors
        if any(term in error for term in ("unit", "scale", "currency"))
    ]
    rendered_dimension_error = _rendered_dimension_error(plan, rendered_answer)
    execution_succeeded = bool(
        verification.get("valid") and execution.get("status") == "ok"
    )
    return {
        "executor_activation_rate": 1.0,
        "all_operands_bound": float(
            bool(operands)
            and bool(verification.get("valid"))
            and len(verified) == len(operands)
            and (not required_slots or len(verified_required) == len(required_slots))
        ),
        "operand_accuracy": operand_accuracy,
        "verified_slot_coverage": (
            len(verified_required) / len(required_slots) if required_slots else None
        ),
        "cell_accuracy": 1.0 - len(cell_errors) / len(operands) if operands else None,
        "operator_accuracy": 1.0 - len(operator_errors) / len(steps) if steps else 1.0,
        "program_accuracy": float(bool(verification.get("valid"))),
        "execution_accuracy": float(execution.get("status") == "ok"),
        "unit_accuracy": float(not unit_errors and not rendered_dimension_error),
        "successful_execution_unit_accuracy": (
            float(not unit_errors and not rendered_dimension_error)
            if execution_succeeded
            else None
        ),
    }


def calculation_status(
    finance: dict[str, Any],
    *,
    applicable: bool,
    rendered_answer: str,
) -> dict[str, str]:
    if not applicable:
        return {"status": "not_applicable", "failure_stage": "not_applicable"}
    plan = dict(finance.get("calculation_plan") or {})
    if not plan:
        return {"status": "measured", "failure_stage": "retrieval_or_plan"}
    verification = dict(finance.get("calculation_verification") or {})
    errors = [str(error) for error in verification.get("errors") or []]
    if any("evidence_missing" in error for error in errors):
        failure_stage = "evidence_binding"
    elif any(
        term in error for error in errors for term in ("unit", "scale", "currency")
    ):
        failure_stage = "unit"
    elif not verification.get("valid"):
        failure_stage = "plan_verification"
    elif dict(finance.get("calculation_execution") or {}).get("status") != "ok":
        failure_stage = "execution"
    elif _rendered_dimension_error(plan, rendered_answer):
        failure_stage = "rendered_unit"
    else:
        failure_stage = "none"
    return {"status": "measured", "failure_stage": failure_stage}


def is_finance_numeric_prediction(prediction: dict[str, Any]) -> bool:
    metadata = dict(prediction.get("evidence_metadata") or {})
    query_plan = dict(metadata.get("query_plan") or {})
    constraints = dict(query_plan.get("constraints") or {})
    domains = (
        constraints.get("verification_domain"),
        prediction.get("verification_domain"),
        prediction.get("dataset_name"),
        prediction.get("dataset_family"),
    )
    if not any("finance" in str(value or "").lower() for value in domains):
        return False
    answer_type = (
        str(query_plan.get("answer_type") or prediction.get("answer_type") or "")
        .strip()
        .lower()
    )
    if not answer_type:
        return True
    return answer_type in {
        "calculation",
        "currency",
        "formula",
        "number",
        "numeric",
        "percentage",
        "ratio",
    }


def _empty_metrics(applicable: bool) -> dict[str, float | None]:
    return {
        "executor_activation_rate": 0.0 if applicable else None,
        "all_operands_bound": 0.0 if applicable else None,
        "operand_accuracy": None,
        "cell_accuracy": None,
        "operator_accuracy": None,
        "program_accuracy": None,
        "execution_accuracy": None,
        "unit_accuracy": None,
        "verified_slot_coverage": None,
        "successful_execution_unit_accuracy": None,
    }


def _rendered_dimension_error(
    plan: dict[str, Any],
    rendered_answer: str,
) -> bool:
    answer = str(rendered_answer or "").lower()
    expected_scale = str(plan.get("answer_scale") or "").strip().lower()
    if expected_scale:
        rendered_scale = next(
            (
                scale
                for scale in ("thousand", "million", "billion")
                if re.search(rf"\b{scale}s?\b", answer)
            ),
            "",
        )
        if rendered_scale != expected_scale:
            return True
    expected_unit = str(plan.get("answer_unit") or "").strip().lower()
    if expected_unit in {"percent", "%"}:
        return "%" not in answer and "percent" not in answer
    return False


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
