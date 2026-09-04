from __future__ import annotations

import re
from typing import Any


def calculation_metrics(
    finance: dict[str, Any],
    *,
    applicable: bool,
    rendered_answer: str,
    gold_numeric_match: float | None = None,
    answerable: bool = True,
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
    cell_errors, operator_errors, unit_errors = _categorized_errors(errors)
    rendered_dimension_error = _rendered_dimension_error(plan, rendered_answer)
    execution_succeeded = bool(
        verification.get("valid") and execution.get("status") == "ok"
    )
    slot_coverage = (
        len(verified_required) / len(required_slots) if required_slots else None
    )
    return {
        "executor_activation_rate": 1.0,
        **_denominator_metrics(
            operands=operands,
            verification=verification,
            verified=verified,
            required_slots=required_slots,
            verified_required=verified_required,
            errors=errors,
            answerable=answerable,
            slot_coverage=slot_coverage,
        ),
        "operand_accuracy": operand_accuracy,
        "verified_slot_coverage": slot_coverage,
        "cell_accuracy": (
            _bounded_accuracy(len(cell_errors), len(operands)) if operands else None
        ),
        "operator_accuracy": (
            _bounded_accuracy(len(operator_errors), len(steps)) if steps else 1.0
        ),
        "program_accuracy": float(bool(verification.get("valid"))),
        "execution_accuracy": float(execution.get("status") == "ok"),
        **_explicit_stage_metrics(
            verification,
            execution,
            gold_numeric_match,
        ),
        "unit_accuracy": float(not unit_errors and not rendered_dimension_error),
        "successful_execution_unit_accuracy": (
            float(not unit_errors and not rendered_dimension_error)
            if execution_succeeded
            else None
        ),
    }


def _denominator_metrics(
    *,
    operands: list[dict[str, Any]],
    verification: dict[str, Any],
    verified: set[str],
    required_slots: list[Any],
    verified_required: set[str],
    errors: list[str],
    answerable: bool,
    slot_coverage: float | None,
) -> dict[str, float | None]:
    bound = float(
        bool(operands)
        and bool(verification.get("valid"))
        and len(verified) == len(operands)
        and (not required_slots or len(verified_required) == len(required_slots))
    )
    missing_detected = bool(
        required_slots
        and len(verified_required) < len(required_slots)
        and any(error.startswith("required_slot_missing:") for error in errors)
    )
    return {
        "all_operands_bound": bound,
        "overall_all_operands_bound": bound,
        "answerable_all_operands_bound": bound if answerable else None,
        "expected_missing_slot_detection": (
            float(missing_detected) if not answerable else None
        ),
        "overall_slot_coverage": slot_coverage,
        "answerable_required_slot_coverage": (slot_coverage if answerable else None),
    }


def _categorized_errors(errors: list[str]) -> tuple[list[str], list[str], list[str]]:
    cell_terms = (
        "evidence_missing",
        "cell_mismatch",
        "value_mismatch",
        "period_mismatch",
    )
    cell_errors = [
        error for error in errors if any(term in error for term in cell_terms)
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
    return cell_errors, operator_errors, unit_errors


def _bounded_accuracy(error_count: int, item_count: int) -> float:
    if item_count <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - error_count / item_count))


def _explicit_stage_metrics(
    verification: dict[str, Any],
    execution: dict[str, Any],
    gold_numeric_match: float | None,
) -> dict[str, float | None]:
    execution_ok = execution.get("status") == "ok"
    return {
        "binding_verifier_pass_rate": float(bool(verification.get("valid"))),
        "program_validity_rate": float(bool(verification.get("valid"))),
        "execution_success_rate": float(execution_ok),
        "executed_answer_accuracy": (
            float(gold_numeric_match)
            if execution_ok and gold_numeric_match is not None
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
        "overall_all_operands_bound": 0.0 if applicable else None,
        "answerable_all_operands_bound": 0.0 if applicable else None,
        "expected_missing_slot_detection": None,
        "overall_slot_coverage": None,
        "answerable_required_slot_coverage": None,
        "operand_accuracy": None,
        "cell_accuracy": None,
        "operator_accuracy": None,
        "program_accuracy": None,
        "execution_accuracy": None,
        "unit_accuracy": None,
        "verified_slot_coverage": None,
        "successful_execution_unit_accuracy": None,
        "binding_verifier_pass_rate": None,
        "program_validity_rate": None,
        "execution_success_rate": None,
        "executed_answer_accuracy": None,
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
