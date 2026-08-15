from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_proposition_evidence import (
    boolean_proposition_authority_level,
    boolean_proposition_candidate_authority_level,
)
from .evidence_identity import identity_of
from .query_evidence_binding_support import slot_item_materialized, slot_semantic_match
from .query_plan_schema import EvidenceSlot, QueryPlan, slot_binding_state
from .selection_assessment_table import SelectionAssessmentTable


def bound_slot_status(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_ids: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
    assessments: SelectionAssessmentTable | None,
) -> str:
    if not evidence_ids:
        return "missing"
    if (
        slot.statement_kind in {"answer_relation", "boolean_proposition"}
        and slot.required_for_verification
        and not slot.required_for_retrieval
    ):
        return _verification_slot_status(
            plan,
            slot,
            evidence_ids,
            evidence_by_identity,
            assessments,
        )
    items = [
        evidence_by_identity[evidence_id]
        for evidence_id in evidence_ids
        if evidence_id in evidence_by_identity
    ]
    state_slot = replace(slot, evidence_ids=evidence_ids)
    return slot_binding_state(
        state_slot,
        items,
        semantic_match=lambda item: slot_semantic_match(
            slot,
            item,
            requires_structure=bool(slot.statement_kind or slot.financial_scope),
        ),
        materialized=lambda item: slot_item_materialized(slot, item),
        provenance_complete=lambda item: bool(identity_of(item).key),
    )


def _verification_slot_status(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_ids: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
    assessments: SelectionAssessmentTable | None,
) -> str:
    if slot.statement_kind == "answer_relation":
        return "retrieved_unverified"
    levels = []
    for evidence_id in evidence_ids:
        item = evidence_by_identity.get(evidence_id)
        if item is None:
            continue
        cached = assessments.get(plan, slot, item) if assessments else None
        levels.append(
            boolean_proposition_candidate_authority_level(
                slot.metric,
                item,
                cached.candidate_score,
            )
            if cached is not None
            else boolean_proposition_authority_level(slot.metric, item)
        )
    if levels and "complete" not in levels and "partial" in levels:
        return "retrieved_partial"
    return "retrieved_unverified"


def binding_trace(
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
