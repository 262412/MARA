from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from . import evidence_binding_policy
from .calculation_evidence_identity import reconcile_materialized_cells
from .deterministic_ranking import quantized_score
from .evidence_identity import identity_of
from .finance_scale import source_page_table_scale_evidence
from .finance_segment_comparison import (
    coherent_segment_evidence_items,
    segment_comparison_evidence_items,
)
from .query_evidence_assessment import bound_slot_status as _bound_slot_status
from .query_evidence_assessment import candidate_assessment_score as _candidate_score
from .query_evidence_assessment import existing_binding_state as _existing_binding_state
from .query_evidence_assessment import (
    is_revenue_operand_slot as _is_revenue_operand_slot,
)
from .query_evidence_assessment import reconcile_boolean_binding_slots
from .query_evidence_binding_support import binding_quality as _binding_quality
from .query_evidence_binding_support import score_evidence_for_slot
from .query_plan_schema import EvidenceSlot, QueryPlan
from .selection_assessment_snapshot import SelectionAssessmentSnapshot

__all__ = [
    "bind_evidence_slots",
    "bind_evidence_slots_monotonic",
    "score_evidence_for_slot",
]


# Retain existing diagnostic and patch entries; candidate rules have one owner.
_candidate_ids_for_slot = evidence_binding_policy.candidate_ids_for_slot
_verification_candidate_ids = evidence_binding_policy.verification_candidate_ids
_segment_comparison_candidate_ids = (
    evidence_binding_policy.segment_comparison_candidate_ids
)
_collection_candidate_ids = evidence_binding_policy.collection_candidate_ids
_dimension_candidate_ids = evidence_binding_policy.dimension_candidate_ids
_distinct_candidate_ids = evidence_binding_policy.distinct_candidate_ids


@dataclass
class _BindingState:
    evidence_by_identity: dict[str, dict[str, Any]]
    bound_slots: list[EvidenceSlot] = field(default_factory=list)
    binding_trace: list[dict[str, Any]] = field(default_factory=list)
    bound_operand_items: list[dict[str, Any]] = field(default_factory=list)
    used_generic_operand_ids: set[str] = field(default_factory=set)
    used_comparison_ids: set[str] = field(default_factory=set)
    used_cross_page_locators: set[tuple[str, str]] = field(default_factory=set)


def bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None = None,
) -> QueryPlan:
    bound, _trace = _bind_evidence_slots(
        plan,
        evidence_items,
        preserve_existing=False,
        assessments=assessments,
    )
    return bound


def bind_evidence_slots_monotonic(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None = None,
) -> tuple[QueryPlan, list[dict[str, Any]]]:
    return _bind_evidence_slots(
        plan,
        evidence_items,
        preserve_existing=True,
        assessments=assessments,
    )


def _bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
    *,
    preserve_existing: bool,
    assessments: SelectionAssessmentSnapshot | None,
) -> tuple[QueryPlan, list[dict[str, Any]]]:
    evidence_items = _binding_evidence_items(plan, evidence_items)
    state = _BindingState(
        evidence_by_identity={identity_of(item).key: item for item in evidence_items}
    )
    for slot in plan.evidence_slots:
        _bind_slot(
            plan,
            slot,
            evidence_items,
            state,
            preserve_existing=preserve_existing,
            assessments=assessments,
        )
    bound_slots = reconcile_boolean_binding_slots(
        plan,
        state.bound_slots,
        state.evidence_by_identity,
        assessments=assessments,
    )
    return replace(plan, evidence_slots=tuple(bound_slots)), state.binding_trace


def _bind_slot(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_items: list[dict[str, Any]],
    state: _BindingState,
    *,
    preserve_existing: bool,
    assessments: SelectionAssessmentSnapshot | None,
) -> None:
    preserved, replacement_reason = _existing_binding_state(
        plan,
        slot,
        state.evidence_by_identity,
        evidence_items,
        requires_structure=bool(plan.constraints.get("requires_structure")),
        assessments=assessments,
    )
    if preserve_existing and preserved:
        state.bound_slots.append(slot)
        state.binding_trace.append(
            _preserved_binding_trace(
                slot,
                state.evidence_by_identity,
                state.bound_operand_items,
                state.used_generic_operand_ids,
            )
        )
        return
    ranked = _ranked_evidence(plan, slot, evidence_items, assessments=assessments)
    evidence_ids = tuple(
        _candidate_ids_for_slot(
            plan,
            slot,
            ranked,
            state.bound_operand_items,
            state.used_generic_operand_ids,
            state.used_comparison_ids,
            state.used_cross_page_locators,
        )
    )
    _update_bound_operand_state(
        slot,
        evidence_ids,
        state.evidence_by_identity,
        state.bound_operand_items,
        state.used_generic_operand_ids,
    )
    state.bound_slots.append(
        replace(
            slot,
            status=_bound_slot_status(
                plan,
                slot,
                evidence_ids,
                state.evidence_by_identity,
                assessments=assessments,
            ),
            evidence_ids=evidence_ids,
        )
    )
    if preserve_existing:
        state.binding_trace.append(
            _binding_trace(
                slot,
                slot.evidence_ids,
                evidence_ids,
                preserved=False,
                replacement_reason=replacement_reason,
            )
        )


def _preserved_binding_trace(
    slot: EvidenceSlot,
    evidence_by_identity: dict[str, dict[str, Any]],
    bound_operand_items: list[dict[str, Any]],
    used_generic_operand_ids: set[str],
) -> dict[str, Any]:
    evidence_ids = slot.evidence_ids
    _update_bound_operand_state(
        slot,
        evidence_ids,
        evidence_by_identity,
        bound_operand_items,
        used_generic_operand_ids,
    )
    return _binding_trace(slot, evidence_ids, evidence_ids, preserved=True)


def _binding_evidence_items(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if plan.constraints.get("comparison_operator") == "proportional_increase":
        evidence_items = segment_comparison_evidence_items(evidence_items)
    elif any(slot.required_for_execution for slot in plan.evidence_slots):
        evidence_items = reconcile_materialized_cells(evidence_items)
    return coherent_segment_evidence_items(plan, evidence_items)


def _ranked_evidence(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_items: list[dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None,
) -> list[tuple[float, int, dict[str, Any]]]:
    ranked = (
        (
            _candidate_score(
                plan,
                slot,
                item,
                assessments=assessments,
            ),
            index,
            item,
        )
        for index, item in enumerate(evidence_items)
    )
    return sorted(
        ranked,
        key=lambda row: (
            -quantized_score(
                row[0]
                + _slot_binding_quality(
                    slot,
                    row[2],
                    evidence_items,
                )
            ),
            -quantized_score(row[0]),
            identity_of(row[2]).key,
        ),
    )


def _update_bound_operand_state(
    slot: EvidenceSlot,
    evidence_ids: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
    bound_operand_items: list[dict[str, Any]],
    used_generic_operand_ids: set[str],
) -> None:
    if slot.role != "operand":
        return
    bound_operand_items.extend(
        evidence_by_identity[evidence_id]
        for evidence_id in evidence_ids
        if evidence_id in evidence_by_identity
    )
    if not slot.period:
        used_generic_operand_ids.update(evidence_ids)


def _binding_trace(
    slot: EvidenceSlot,
    before_ids: tuple[str, ...],
    after_ids: tuple[str, ...],
    *,
    preserved: bool,
    replacement_reason: str = "",
) -> dict[str, Any]:
    return {
        "slot_id": slot.slot_id,
        "preserved_existing_binding": preserved,
        "replacement_reason": replacement_reason,
        "before_identity": before_ids[0] if before_ids else "",
        "after_identity": after_ids[0] if after_ids else "",
    }


def _slot_binding_quality(
    slot: EvidenceSlot,
    item: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> float:
    quality = _binding_quality(slot, item)
    if not _is_revenue_operand_slot(slot):
        return quality
    local_scale, _evidence_id = source_page_table_scale_evidence(
        item,
        evidence_items,
    )
    return quality + (2.0 if local_scale else 0.0)
