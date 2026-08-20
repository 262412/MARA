from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

from .boolean_proposition_evidence import boolean_proposition_authority_level
from .cross_page_boolean_authority import reconcile_cross_page_boolean_proposition
from .evidence_identity import identity_of
from .finance_query_planning import finance_revenue_row_quality
from .finance_scale import source_page_table_scale_evidence
from .financial_statement_identity import source_identity
from .query_evidence_binding_support import (
    candidate_score_for_slot,
    score_evidence_for_slot,
    slot_item_materialized,
    slot_semantic_match,
    trusted_dimension_item,
)
from .query_plan_schema import (
    EvidenceSlot,
    QueryPlan,
    required_slot_count,
    slot_binding_state,
)
from .selection_assessment_snapshot import SelectionAssessmentSnapshot


def candidate_assessment_score(
    plan: QueryPlan,
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    assessments: SelectionAssessmentSnapshot | None,
) -> float:
    if assessments is not None:
        return assessments.candidate_score(plan, slot, item)
    return candidate_score_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )


def existing_binding_state(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_by_identity: dict[str, dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    *,
    requires_structure: bool,
    assessments: SelectionAssessmentSnapshot | None,
) -> tuple[bool, str]:
    if (
        slot.status
        not in {
            "filled",
            "retrieved_partial",
            "retrieved_unverified",
            "verified_support",
            "verified_conflict",
        }
        or not slot.evidence_ids
    ):
        return False, "missing_existing_binding"
    if len(slot.evidence_ids) < required_slot_count(slot):
        return False, "incomplete_existing_binding"
    items = [evidence_by_identity.get(evidence_id) for evidence_id in slot.evidence_ids]
    if any(item is None for item in items):
        return False, "unresolved_existing_identity"
    resolved_items = [item for item in items if item is not None]
    if any(
        _existing_binding_score(
            plan,
            slot,
            item,
            requires_structure=requires_structure,
            assessments=assessments,
        )
        <= 0
        for item in resolved_items
    ):
        return False, "incompatible_existing_binding"
    if slot.role == "dimension" and any(
        not trusted_dimension_item(item) for item in resolved_items
    ):
        return False, "incompatible_existing_binding"
    if (
        slot_binding_state(
            slot,
            resolved_items,
            semantic_match=lambda item: _semantic_match(
                plan,
                slot,
                item,
                requires_structure=requires_structure,
                assessments=assessments,
            ),
            materialized=lambda item: slot_item_materialized(slot, item),
            provenance_complete=lambda item: bool(identity_of(item).key),
        )
        != "filled"
    ):
        return False, "incomplete_existing_binding"
    if _provenance_complete_revenue_equivalent_available(
        slot,
        items,
        evidence_items,
        requires_structure=requires_structure,
    ):
        return False, "provenance_complete_equivalent_available"
    return True, ""


def bound_slot_status(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_ids: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None,
) -> str:
    if not evidence_ids:
        return "missing"
    if (
        slot.statement_kind in {"answer_relation", "boolean_proposition"}
        and slot.required_for_verification
        and not slot.required_for_retrieval
    ):
        if slot.statement_kind == "answer_relation":
            return "retrieved_unverified"
        levels = [
            (
                assessments.authority_level(
                    plan,
                    slot,
                    evidence_by_identity[evidence_id],
                )
                if assessments is not None
                else boolean_proposition_authority_level(
                    slot.query or slot.metric,
                    evidence_by_identity[evidence_id],
                )
            )
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_identity
        ]
        if levels and "complete" not in levels and "partial" in levels:
            return "retrieved_partial"
        return "retrieved_unverified"
    items = [
        evidence_by_identity[evidence_id]
        for evidence_id in evidence_ids
        if evidence_id in evidence_by_identity
    ]
    state_slot = replace(slot, evidence_ids=evidence_ids)
    return slot_binding_state(
        state_slot,
        items,
        semantic_match=lambda item: _semantic_match(
            plan,
            slot,
            item,
            requires_structure=bool(slot.statement_kind or slot.financial_scope),
            assessments=assessments,
        ),
        materialized=lambda item: slot_item_materialized(slot, item),
        provenance_complete=lambda item: bool(identity_of(item).key),
    )


def reconcile_boolean_binding_slots(
    plan: QueryPlan,
    bound_slots: list[EvidenceSlot],
    evidence_by_identity: dict[str, dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None,
) -> list[EvidenceSlot]:
    return reconcile_cross_page_boolean_proposition(
        plan,
        bound_slots,
        evidence_by_identity,
        status_for=lambda slot, evidence_ids, by_identity: bound_slot_status(
            plan,
            slot,
            evidence_ids,
            by_identity,
            assessments=assessments,
        ),
        assessments=assessments,
    )


def is_revenue_operand_slot(slot: EvidenceSlot) -> bool:
    return slot.role == "operand" and slot.metric in {"net sales", "revenue"}


def _existing_binding_score(
    plan: QueryPlan,
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool,
    assessments: SelectionAssessmentSnapshot | None,
) -> float:
    if assessments is not None and slot.statement_kind == "boolean_proposition":
        if slot.status in {"retrieved_partial", "retrieved_unverified"}:
            return assessments.candidate_score(plan, slot, item)
        return float(assessments.authority_level(plan, slot, item) != "none")
    if slot.status in {"retrieved_partial", "retrieved_unverified"}:
        return candidate_score_for_slot(
            slot,
            item,
            requires_structure=requires_structure,
        )
    return score_evidence_for_slot(
        slot,
        item,
        requires_structure=requires_structure,
    )


def _semantic_match(
    plan: QueryPlan,
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool,
    assessments: SelectionAssessmentSnapshot | None,
) -> bool:
    if assessments is not None and slot.statement_kind == "boolean_proposition":
        return assessments.candidate_score(plan, slot, item) > 0
    return slot_semantic_match(
        slot,
        item,
        requires_structure=requires_structure,
    )


def _provenance_complete_revenue_equivalent_available(
    slot: EvidenceSlot,
    existing_items: list[dict[str, Any] | None],
    evidence_items: list[dict[str, Any]],
    *,
    requires_structure: bool,
) -> bool:
    if not is_revenue_operand_slot(slot) or len(existing_items) != 1:
        return False
    existing = existing_items[0]
    if existing is None:
        return False
    existing_scale, _existing_scale_id = source_page_table_scale_evidence(
        existing,
        evidence_items,
    )
    if existing_scale:
        return False
    return any(
        identity_of(candidate).key != identity_of(existing).key
        and _equivalent_revenue_operand(existing, candidate)
        and candidate_score_for_slot(
            slot,
            candidate,
            requires_structure=requires_structure,
        )
        > 0
        and bool(source_page_table_scale_evidence(candidate, evidence_items)[0])
        for candidate in evidence_items
    )


def _equivalent_revenue_operand(
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    existing_source = source_identity(existing)
    candidate_source = source_identity(candidate)
    return bool(
        existing_source
        and existing_source == candidate_source
        and str(existing.get("period") or existing.get("column_label") or "").strip()
        == str(candidate.get("period") or candidate.get("column_label") or "").strip()
        and _same_numeric_value(existing.get("value"), candidate.get("value"))
        and str(existing.get("statement_kind") or "").strip()
        == str(candidate.get("statement_kind") or "").strip()
        and str(existing.get("financial_scope") or "").strip()
        == str(candidate.get("financial_scope") or "").strip()
        and finance_revenue_row_quality(
            "revenue",
            str(existing.get("row_label") or ""),
        )
        and finance_revenue_row_quality(
            "revenue",
            str(candidate.get("row_label") or ""),
        )
    )


def _same_numeric_value(left: Any, right: Any) -> bool:
    if left in (None, "") or right in (None, ""):
        return False
    try:
        return Decimal(str(left).replace(",", "")) == Decimal(
            str(right).replace(",", "")
        )
    except InvalidOperation:
        return False
