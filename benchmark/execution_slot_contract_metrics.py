from __future__ import annotations

from collections import Counter
from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_calculation_binding import item_dimension
from ktem.docqa.finance_scale import (
    compatible_dimension_scope,
    dimension_binding_scope,
    valid_dimension_binding_scope,
    valid_dimension_evidence_identity,
)
from ktem.docqa.query_evidence_constraints import executable_operand_evidence
from ktem.docqa.query_plan_schema import (
    evidence_slot_references_are_bound,
    plan_from_payload,
)
from ktem.docqa.query_planning import score_evidence_for_slot

from .metrics import is_abstention_answer


def required_slot_reference_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, float | None]:
    payload = metadata.get("query_plan")
    if not isinstance(payload, dict) or not isinstance(
        payload.get("evidence_slots"),
        list,
    ):
        return _metric_payload(Counter())
    plan = plan_from_payload(
        str(prediction.get("question") or ""),
        answer_type=str(
            payload.get("answer_type") or prediction.get("answer_type") or ""
        ),
        verification_domain=str(
            dict(payload.get("constraints") or {}).get("verification_domain")
            or prediction.get("verification_domain")
            or ""
        ),
        payload=payload,
    )
    lookup = unambiguous_evidence_alias_lookup(items)
    requires_structure = bool(plan.constraints.get("requires_structure"))
    calculation_operands = _calculation_operands(metadata)
    verified_execution_slots = _verified_execution_slots(metadata)
    audit_execution = any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in prediction.get("gold_answers") or []
    )
    counts: Counter[str] = Counter()
    for slot in plan.evidence_slots:
        counts.update(
            _audit_slot_reference(
                slot,
                lookup,
                calculation_operands,
                verified_execution_slots,
                requires_structure=requires_structure,
                audit_execution=audit_execution,
            )
        )
    counts.update(
        _audit_effective_scale_coverage(
            calculation_operands,
            lookup,
            audit_execution=audit_execution,
        )
    )
    return _metric_payload(counts)


def _audit_slot_reference(
    slot: Any,
    lookup: dict[str, dict[str, Any]],
    calculation_operands: list[dict[str, Any]],
    verified_execution_slots: set[str],
    *,
    requires_structure: bool,
    audit_execution: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    required = bool(
        slot.required
        or slot.required_for_retrieval
        or slot.required_for_execution
        or slot.required_for_verification
    )
    if not required:
        return counts
    execution_required = bool(slot.required_for_execution and audit_execution)
    execution_operand = bool(execution_required and slot.role == "operand")
    execution_dimension = bool(execution_required and slot.role == "dimension")
    counts["execution_operand_slot_count"] += int(execution_operand)
    counts["execution_dimension_slot_count"] += int(execution_dimension)
    counts["execution_other_slot_count"] += int(
        execution_required and not execution_operand and not execution_dimension
    )
    if not evidence_slot_references_are_bound(slot):
        return counts
    counts["reference_count"] += len(slot.evidence_ids)
    resolved = [
        lookup[evidence_id]
        for evidence_id in slot.evidence_ids
        if evidence_id in lookup
    ]
    counts["resolved_reference_count"] += len(resolved)
    if not resolved:
        counts["unresolved_references"] += len(slot.evidence_ids) or 1
        return counts
    if execution_operand:
        counts.update(
            _audit_execution_operand_slot(
                slot,
                resolved,
                calculation_operands,
                verified_execution_slots,
                requires_structure=requires_structure,
            )
        )
    elif execution_dimension:
        counts.update(
            _audit_execution_dimension_slot(
                slot,
                resolved,
                calculation_operands,
                lookup,
                requires_structure=requires_structure,
            )
        )
    if _has_match_constraints(slot) and not any(
        score_evidence_for_slot(
            slot,
            item,
            requires_structure=requires_structure,
        )
        > 0
        for item in resolved
    ):
        counts["semantic_false_fills"] += 1
    return counts


def _audit_execution_operand_slot(
    slot: Any,
    resolved: list[dict[str, Any]],
    calculation_operands: list[dict[str, Any]],
    verified_execution_slots: set[str],
    *,
    requires_structure: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    executable = [item for item in resolved if executable_operand_evidence(item)]
    if executable:
        counts["atomic_execution_slots"] = 1
        counts["materialized_execution_slots"] = 1
    else:
        counts["parent_false_fills"] = int(
            any(identity_of(item).kind not in {"cell", "span"} for item in resolved)
        )
        counts["header_value_violations"] = int(
            any(_header_or_period_value(item) for item in resolved)
        )
    matching = [
        item
        for item in executable
        if score_evidence_for_slot(
            slot,
            item,
            requires_structure=requires_structure,
        )
        > 0
    ]
    if not matching:
        return counts
    counts["bound_execution_slots"] = 1
    matching_ids = {identity_of(item).key for item in matching}
    counts["resolved_execution_operands"] = int(
        slot.slot_id in verified_execution_slots
        or any(
            str(operand.get("evidence_identity") or operand.get("evidence_id") or "")
            in matching_ids
            for operand in calculation_operands
        )
    )
    return counts


def _audit_execution_dimension_slot(
    slot: Any,
    resolved: list[dict[str, Any]],
    calculation_operands: list[dict[str, Any]],
    lookup: dict[str, dict[str, Any]],
    *,
    requires_structure: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    matching = [
        item
        for item in resolved
        if score_evidence_for_slot(
            slot,
            item,
            requires_structure=requires_structure,
        )
        > 0
    ]
    if not matching:
        return counts
    counts["bound_dimension_slots"] = 1
    operand_items = [
        lookup[evidence_id]
        for operand in calculation_operands
        if (
            evidence_id := str(
                operand.get("evidence_identity") or operand.get("evidence_id") or ""
            )
        )
        and evidence_id in lookup
    ]
    if not operand_items or any(
        compatible_dimension_scope(operand, dimension)
        for operand in operand_items
        for dimension in matching
    ):
        counts["scope_valid_dimension_slots"] = 1
    return counts


def _metric_payload(counts: Counter[str]) -> dict[str, float | None]:
    operand_count = counts["execution_operand_slot_count"]
    dimension_count = counts["execution_dimension_slot_count"]
    reference_count = counts["reference_count"]
    return {
        "slot_semantic_false_fill_count": float(counts["semantic_false_fills"]),
        "slot_unresolved_reference_count": float(counts["unresolved_references"]),
        "plan_evidence_reference_resolution_rate": (
            counts["resolved_reference_count"] / reference_count
            if reference_count
            else None
        ),
        "execution_slot_atomicity_rate": _rate(
            counts["atomic_execution_slots"],
            operand_count,
        ),
        "execution_slot_materialization_rate": _rate(
            counts["materialized_execution_slots"],
            operand_count,
        ),
        "execution_slot_binding_rate": _rate(
            counts["bound_execution_slots"],
            operand_count,
        ),
        "execution_operand_resolution_rate": _rate(
            counts["resolved_execution_operands"],
            operand_count,
        ),
        "execution_slot_atomicity_violation_count": float(
            operand_count - counts["atomic_execution_slots"]
        ),
        "parent_table_false_fill_count": float(counts["parent_false_fills"]),
        "header_as_value_violation_count": float(counts["header_value_violations"]),
        "execution_operand_slot_count": float(operand_count),
        "execution_dimension_slot_count": float(dimension_count),
        "execution_other_slot_count": float(counts["execution_other_slot_count"]),
        "dimension_binding_rate": _rate(
            counts["bound_dimension_slots"],
            dimension_count,
        ),
        "dimension_scope_rate": _rate(
            counts["scope_valid_dimension_slots"],
            dimension_count,
        ),
        "dimension_binding_violation_count": float(
            dimension_count - counts["bound_dimension_slots"]
        ),
        "dimension_scope_violation_count": float(
            dimension_count - counts["scope_valid_dimension_slots"]
        ),
        "effective_scale_operand_count": float(counts["effective_scale_operand_count"]),
        "effective_scale_bound_operand_count": float(
            counts["effective_scale_bound_operand_count"]
        ),
        "effective_scale_coverage_rate": _rate(
            counts["effective_scale_bound_operand_count"],
            counts["effective_scale_operand_count"],
        ),
        "effective_scale_missing_count": float(counts["effective_scale_missing_count"]),
    }


def _audit_effective_scale_coverage(
    calculation_operands: list[dict[str, Any]],
    lookup: dict[str, dict[str, Any]],
    *,
    audit_execution: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not audit_execution:
        return counts
    operands = [
        operand
        for operand in calculation_operands
        if str(operand.get("query_slot_id") or "").startswith("operand:")
        or not str(operand.get("query_slot_id") or "").strip()
    ]
    counts["effective_scale_operand_count"] = len(operands)
    counts["effective_scale_bound_operand_count"] = sum(
        _has_effective_scale_provenance(operand, lookup) for operand in operands
    )
    counts["effective_scale_missing_count"] = (
        counts["effective_scale_operand_count"]
        - counts["effective_scale_bound_operand_count"]
    )
    return counts


def _has_effective_scale_provenance(
    operand: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
) -> bool:
    scale = str(operand.get("scale") or "").strip().lower()
    operand_identity = str(
        operand.get("evidence_identity") or operand.get("evidence_id") or ""
    ).strip()
    evidence_identity = str(
        operand.get("scale_evidence_identity") or operand.get("scale_evidence_id") or ""
    ).strip()
    scope = str(operand.get("dimension_binding_scope") or "").strip()
    operand_item = lookup.get(operand_identity)
    dimension_item = lookup.get(evidence_identity)
    if (
        scale == "one"
        and scope == "operand_local"
        and operand_identity
        and operand_identity == evidence_identity
        and operand_item
        and dimension_item
    ):
        return bool(
            str(operand.get("unit") or operand.get("currency") or "").strip()
            and item_dimension(operand_item, "scale_provenance")
            == "local_currency_amount"
            and dimension_binding_scope(operand_item, dimension_item) == scope
        )
    return bool(
        scale
        and valid_dimension_evidence_identity(evidence_identity)
        and valid_dimension_binding_scope(scope)
        and operand_item
        and dimension_item
        and compatible_dimension_scope(operand_item, dimension_item)
        and dimension_binding_scope(operand_item, dimension_item) == scope
    )


def _calculation_operands(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return []
    plan = trace.get("calculation_plan")
    if not isinstance(plan, dict):
        return []
    return _records(plan.get("operands"))


def _verified_execution_slots(metadata: dict[str, Any]) -> set[str]:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return set()
    verification = trace.get("calculation_verification")
    execution = trace.get("calculation_execution")
    if (
        not isinstance(verification, dict)
        or not verification.get("valid")
        or not isinstance(execution, dict)
        or execution.get("status") != "ok"
    ):
        return set()
    return {
        str(value).strip()
        for value in verification.get("verified_required_slot_ids") or []
        if str(value or "").strip()
    }


def _has_match_constraints(slot: Any) -> bool:
    locator = slot.locator.as_dict() if slot.locator is not None else {}
    return bool(
        locator
        or slot.entity
        or slot.metric
        or slot.period
        or slot.period_kind
        or slot.unit
        or slot.scale
        or slot.statement_kind
        or slot.financial_scope
        or slot.modality not in {"", "auto"}
    )


def _header_or_period_value(item: dict[str, Any]) -> bool:
    period = str(item.get("period") or item.get("column_label") or "")
    value = str(item.get("value") or "")
    return str(item.get("cell_role") or "").lower() == "header" or (
        period == value and value.isdigit()
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _records(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]
