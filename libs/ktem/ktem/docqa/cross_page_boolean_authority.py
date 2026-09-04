from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from .boolean_evidence_scope import boolean_proposition_evidence_score
from .query_evidence_text import evidence_text
from .query_phrase_extraction import source_page_locator
from .query_plan_schema import EvidenceSlot, QueryPlan
from .selection_assessment_snapshot import SelectionAssessmentSnapshot

SlotStatus = Callable[
    [EvidenceSlot, tuple[str, ...], dict[str, dict[str, Any]]],
    str,
]


def reconcile_cross_page_boolean_proposition(
    plan: QueryPlan,
    bound_slots: list[EvidenceSlot],
    evidence_by_identity: dict[str, dict[str, Any]],
    *,
    status_for: SlotStatus,
    assessments: SelectionAssessmentSnapshot | None = None,
) -> list[EvidenceSlot]:
    explicit_pages = tuple(
        str(value).strip()
        for value in plan.constraints.get("explicit_page_labels") or ()
        if str(value).strip()
    )
    if (
        plan.answer_type != "boolean"
        or plan.question_type != "cross_page"
        or len(explicit_pages) != 2
    ):
        return bound_slots
    proposition_index = next(
        (
            index
            for index, slot in enumerate(bound_slots)
            if slot.slot_id == "support:proposition"
            and slot.statement_kind == "boolean_proposition"
        ),
        None,
    )
    page_slots = [
        slot
        for slot_id in ("support:left_subject", "support:right_subject")
        for slot in bound_slots
        if slot.slot_id == slot_id
    ]
    if proposition_index is None or len(page_slots) != 2:
        return bound_slots
    proposition = bound_slots[proposition_index]
    proposition_ids = _proposition_ids(
        plan,
        proposition,
        page_slots,
        explicit_pages,
        evidence_by_identity,
        assessments=assessments,
    )
    reconciled = list(bound_slots)
    reconciled[proposition_index] = replace(
        proposition,
        status=status_for(proposition, proposition_ids, evidence_by_identity),
        evidence_ids=proposition_ids,
    )
    return reconciled


def _proposition_ids(
    plan: QueryPlan,
    proposition: EvidenceSlot,
    page_slots: list[EvidenceSlot],
    explicit_pages: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
    *,
    assessments: SelectionAssessmentSnapshot | None,
) -> tuple[str, ...]:
    if any(len(slot.evidence_ids) != 1 for slot in page_slots):
        return ()
    identities = tuple(slot.evidence_ids[0] for slot in page_slots)
    if len(set(identities)) != len(identities):
        return ()
    items = [evidence_by_identity.get(identity) for identity in identities]
    if any(item is None for item in items):
        return ()
    resolved_items = [item for item in items if item is not None]
    page_labels = tuple(source_page_locator(item)[1] for item in resolved_items)
    if page_labels != explicit_pages or len(set(page_labels)) != len(page_labels):
        return ()
    if any(_graph_evidence(item) for item in resolved_items):
        return ()
    if _duplicate_content(resolved_items):
        return ()
    if any(
        (
            assessments.authority_level(plan, proposition, item) == "none"
            if assessments is not None
            else boolean_proposition_evidence_score(proposition.metric, item) <= 0
        )
        for item in resolved_items
    ):
        return ()
    return identities


def _graph_evidence(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return any(
        str(item.get(field) or nested.get(field) or "")
        .strip()
        .lower()
        .startswith("graph")
        for field in ("modality", "element_type", "evidence_level")
    )


def _duplicate_content(items: list[dict[str, Any]]) -> bool:
    hashes = [str(item.get("normalized_text_hash") or "").strip() for item in items]
    if all(hashes) and len(set(hashes)) != len(hashes):
        return True
    normalized_texts = [
        " ".join(evidence_text(item).casefold().split()) for item in items
    ]
    return bool(
        all(normalized_texts) and len(set(normalized_texts)) != len(normalized_texts)
    )
