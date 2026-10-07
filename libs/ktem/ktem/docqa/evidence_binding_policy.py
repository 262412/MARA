"""Choose IDs from ranked evidence using the existing specialized rules.

Ranking, assessments and binding status belong to the binder. Used-ID and page
sets remain caller-owned and are deliberately updated at the original stage.
"""

from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .finance_narrative_evidence import authoritative_narrative_candidate_ids
from .finance_scale import source_scale_evidence
from .query_evidence_binding_support import agreement_attributes, item_for_raw_id
from .query_phrase_extraction import source_page_locator
from .query_plan_schema import EvidenceSlot, QueryPlan


def candidate_ids_for_slot(
    plan: QueryPlan,
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
    bound_operand_items: list[dict[str, Any]],
    used_generic_operand_ids: set[str],
    used_comparison_ids: set[str],
    used_cross_page_locators: set[tuple[str, str]],
) -> list[str]:
    verification_ids = verification_candidate_ids(slot, ranked)
    if verification_ids is not None:
        return verification_ids
    segment_ids = segment_comparison_candidate_ids(plan, slot, ranked)
    if segment_ids is not None:
        return segment_ids
    if (
        slot.role == "operand"
        and str(slot.operator_role or "").lower() == "collection"
        and max(1, slot.cardinality) > 1
    ):
        return collection_candidate_ids(slot, ranked)
    candidate_ids = (
        dimension_candidate_ids(slot, ranked, bound_operand_items)
        if slot.role == "dimension"
        else [identity_of(item).key for score, _index, item in ranked[:3] if score > 0]
    )
    narrative_ids = (
        authoritative_narrative_candidate_ids(slot.metric, ranked)
        if slot.role == "support"
        else None
    )
    if narrative_ids is not None:
        candidate_ids = list(narrative_ids)
    distinct_slot_ids = set(plan.constraints.get("distinct_source_page_slot_ids") or [])
    if plan.constraints.get("requires_distinct_evidence") and (
        slot.slot_id in distinct_slot_ids
        or (not distinct_slot_ids and slot.role in {"support", "operand"})
    ):
        candidate_ids = distinct_candidate_ids(
            ranked,
            plan,
            used_comparison_ids,
            used_cross_page_locators,
        )
    if slot.role == "operand" and not slot.period:
        candidate_ids = [
            evidence_id
            for evidence_id in candidate_ids
            if evidence_id not in used_generic_operand_ids
        ][:1]
    return (
        candidate_ids[: max(1, slot.cardinality)]
        if slot.role == "operand"
        else candidate_ids
    )


def verification_candidate_ids(
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
) -> list[str] | None:
    if not (
        slot.required_for_verification
        and not slot.required_for_retrieval
        and slot.statement_kind in {"answer_relation", "boolean_proposition"}
    ):
        return None
    return [
        identity_of(item).key
        for score, _index, item in ranked[: max(3, slot.cardinality)]
        if slot.statement_kind == "answer_relation" or score > 0
    ]


def segment_comparison_candidate_ids(
    plan: QueryPlan,
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
) -> list[str] | None:
    if (
        plan.constraints.get("comparison_operator") != "proportional_increase"
        or slot.role != "support"
        or slot.statement_kind != "segment_table"
        or slot.financial_scope != "segment"
        or not slot.period
    ):
        return None
    return [
        identity_of(item).key
        for _score, _index, item in ranked
        if str(item.get("period") or item.get("column_label") or "") == slot.period
    ]


def collection_candidate_ids(
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
) -> list[str]:
    selected: list[str] = []
    facilities: set[str] = set()
    for score, _index, item in ranked:
        if score <= 0:
            continue
        attributes = agreement_attributes(item)
        if slot.metric == "revolving credit capacity" and slot.entity.startswith(
            "active"
        ):
            if attributes["agreement_lifecycle_status"] != "active":
                continue
            as_of_date = slot.entity.removeprefix("active_at:")
            effective_date = attributes["effective_date"]
            if (
                slot.entity.startswith("active_at:")
                and effective_date
                and effective_date > as_of_date
            ):
                continue
        facility = attributes["facility_identity"] or identity_of(item).key
        if facility in facilities:
            continue
        facilities.add(facility)
        selected.append(identity_of(item).key)
        if len(selected) >= max(1, slot.cardinality):
            break
    return selected


def dimension_candidate_ids(
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
    operand_items: list[dict[str, Any]],
) -> list[str]:
    selected: list[str] = []
    evidence_items = [item for _score, _index, item in ranked]
    for operand in operand_items:
        scale, raw_evidence_id = source_scale_evidence(operand, evidence_items)
        if not scale or (slot.scale and slot.scale != scale):
            continue
        item = item_for_raw_id(raw_evidence_id, evidence_items)
        if item is None:
            continue
        identity = identity_of(item).key
        if identity not in selected:
            selected.append(identity)
    return selected


def distinct_candidate_ids(
    ranked: list[tuple[float, int, dict[str, Any]]],
    plan: QueryPlan,
    used_ids: set[str],
    used_locators: set[tuple[str, str]],
) -> list[str]:
    for score, _index, item in ranked:
        identity = identity_of(item).key
        locator = source_page_locator(item)
        requires_distinct_pages = bool(
            plan.constraints.get("requires_distinct_source_pages")
        )
        if (
            score <= 0
            or identity in used_ids
            or (
                requires_distinct_pages and (not locator[1] or locator in used_locators)
            )
        ):
            continue
        used_ids.add(identity)
        if requires_distinct_pages:
            used_locators.add(locator)
        return [identity]
    return []
