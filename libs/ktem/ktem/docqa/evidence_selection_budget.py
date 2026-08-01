from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .execution_slot_lineage import (
    is_atomic_operand_candidate,
    linked_dimension_candidate,
    linked_parent_candidate,
)
from .query_plan_schema import QueryPlan
from .required_slot_selection import (
    EXECUTION_SLOT_PARENT_QUOTA,
    REQUIRED_SLOT_CANDIDATE_QUOTA,
    slot_score,
)


def evidence_selection_budget_trace(
    plan: QueryPlan,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    return {
        "candidate_budget_partitions": _candidate_budget_partitions(plan),
        "selected_budget_usage": _selected_budget_usage(
            plan,
            candidates,
            selected,
        ),
    }


def slot_candidate_reasons(
    plan: QueryPlan,
    slot: Any,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    selected_ids = {identity_of(item).key for item in selected}
    chosen: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for item in candidates:
        identity = identity_of(item).key
        score = slot_score(plan, slot, item)
        if identity in selected_ids and score > 0:
            chosen.append(
                _candidate_reason(identity, "semantic_slot_match_selected", score)
            )
            continue
        if score <= 0:
            reason = "semantic_slot_mismatch"
        elif (
            slot.required_for_execution
            and slot.role == "operand"
            and not is_atomic_operand_candidate(item)
        ):
            reason = "non_atomic_parent_reserved_for_lineage"
        else:
            reason = "compatible_candidate_outside_slot_quota"
        dropped.append(_candidate_reason(identity, reason, score))
    return {
        "candidate_selection_reasons": chosen,
        "candidate_drop_reasons": dropped,
    }


def _candidate_reason(identity: str, reason: str, score: float) -> dict[str, Any]:
    return {
        "evidence_id": identity,
        "reason": reason,
        "slot_score": score,
    }


def _candidate_budget_partitions(plan: QueryPlan) -> dict[str, int]:
    required_slots = [
        slot for slot in plan.evidence_slots if slot.required_for_retrieval
    ]
    execution_operands = [
        slot
        for slot in required_slots
        if slot.required_for_execution and slot.role == "operand"
    ]
    dimensions = [slot for slot in required_slots if slot.role == "dimension"]
    factual = [
        slot
        for slot in required_slots
        if slot not in execution_operands and slot not in dimensions
    ]
    return {
        "factual_narrative": len(factual) * REQUIRED_SLOT_CANDIDATE_QUOTA,
        "execution_operands": (len(execution_operands) * REQUIRED_SLOT_CANDIDATE_QUOTA),
        "parent_tables": len(execution_operands) * EXECUTION_SLOT_PARENT_QUOTA,
        "dimensions": len(dimensions) * REQUIRED_SLOT_CANDIDATE_QUOTA,
    }


def _selected_budget_usage(
    plan: QueryPlan,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> dict[str, int]:
    selected_by_id = {identity_of(item).key: item for item in selected}
    operand_ids = {
        evidence_id
        for slot in plan.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
        for evidence_id in slot.evidence_ids
        if evidence_id in selected_by_id
    }
    dimension_ids = {
        evidence_id
        for slot in plan.evidence_slots
        if slot.role == "dimension"
        for evidence_id in slot.evidence_ids
        if evidence_id in selected_by_id
    }
    parent_ids: set[str] = set()
    for evidence_id in operand_ids:
        operand = selected_by_id[evidence_id]
        parent = linked_parent_candidate(operand, candidates)
        if parent is not None and identity_of(parent).key in selected_by_id:
            parent_ids.add(identity_of(parent).key)
        dimension = linked_dimension_candidate(operand, candidates)
        if dimension is not None and identity_of(dimension).key in selected_by_id:
            dimension_ids.add(identity_of(dimension).key)
    classified = operand_ids | dimension_ids | parent_ids
    return {
        "factual_narrative": len(set(selected_by_id) - classified),
        "execution_operands": len(operand_ids),
        "parent_tables": len(parent_ids - dimension_ids),
        "dimensions": len(dimension_ids),
    }
