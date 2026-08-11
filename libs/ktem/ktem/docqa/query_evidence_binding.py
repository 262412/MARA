from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_proposition_evidence import boolean_proposition_authority_level
from .calculation_evidence_identity import reconcile_materialized_cells
from .cross_page_boolean_authority import reconcile_cross_page_boolean_proposition
from .deterministic_ranking import quantized_score
from .evidence_identity import identity_of
from .finance_narrative_evidence import authoritative_narrative_candidate_ids
from .finance_scale import source_scale_evidence
from .finance_segment_comparison import (
    coherent_segment_evidence_items,
    segment_comparison_evidence_items,
)
from .query_evidence_binding_support import (
    agreement_attributes as _agreement_attributes,
)
from .query_evidence_binding_support import binding_quality as _binding_quality
from .query_evidence_binding_support import (
    candidate_score_for_slot as _candidate_score_for_slot,
)
from .query_evidence_binding_support import item_for_raw_id as _item_for_raw_id
from .query_evidence_binding_support import score_evidence_for_slot
from .query_evidence_binding_support import (
    trusted_dimension_item as _trusted_dimension_item,
)
from .query_phrase_extraction import source_page_locator
from .query_plan_schema import EvidenceSlot, QueryPlan


def bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> QueryPlan:
    bound, _trace = _bind_evidence_slots(
        plan,
        evidence_items,
        preserve_existing=False,
    )
    return bound


def bind_evidence_slots_monotonic(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> tuple[QueryPlan, list[dict[str, Any]]]:
    return _bind_evidence_slots(plan, evidence_items, preserve_existing=True)


def _bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
    *,
    preserve_existing: bool,
) -> tuple[QueryPlan, list[dict[str, Any]]]:
    evidence_items = _binding_evidence_items(plan, evidence_items)
    bound_slots = []
    binding_trace: list[dict[str, Any]] = []
    used_generic_operand_ids: set[str] = set()
    used_comparison_ids: set[str] = set()
    used_cross_page_locators: set[tuple[str, str]] = set()
    evidence_by_identity = {identity_of(item).key: item for item in evidence_items}
    bound_operand_items: list[dict[str, Any]] = []
    for slot in plan.evidence_slots:
        preserved, replacement_reason = _existing_binding_state(
            slot,
            evidence_by_identity,
            requires_structure=bool(plan.constraints.get("requires_structure")),
        )
        if preserve_existing and preserved:
            evidence_ids = slot.evidence_ids
            _update_bound_operand_state(
                slot,
                evidence_ids,
                evidence_by_identity,
                bound_operand_items,
                used_generic_operand_ids,
            )
            bound_slots.append(slot)
            binding_trace.append(
                _binding_trace(slot, evidence_ids, evidence_ids, preserved=True)
            )
            continue
        ranked = _ranked_evidence(plan, slot, evidence_items)
        candidate_ids = _candidate_ids_for_slot(
            plan,
            slot,
            ranked,
            bound_operand_items,
            used_generic_operand_ids,
            used_comparison_ids,
            used_cross_page_locators,
        )
        evidence_ids = tuple(candidate_ids)
        _update_bound_operand_state(
            slot,
            evidence_ids,
            evidence_by_identity,
            bound_operand_items,
            used_generic_operand_ids,
        )
        bound_slots.append(
            replace(
                slot,
                status=_bound_slot_status(
                    slot,
                    evidence_ids,
                    evidence_by_identity,
                ),
                evidence_ids=evidence_ids,
            )
        )
        if preserve_existing:
            binding_trace.append(
                _binding_trace(
                    slot,
                    slot.evidence_ids,
                    evidence_ids,
                    preserved=False,
                    replacement_reason=replacement_reason,
                )
            )
    bound_slots = reconcile_cross_page_boolean_proposition(
        plan, bound_slots, evidence_by_identity, status_for=_bound_slot_status
    )
    return replace(plan, evidence_slots=tuple(bound_slots)), binding_trace


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
) -> list[tuple[float, int, dict[str, Any]]]:
    ranked = (
        (
            _candidate_score_for_slot(
                slot,
                item,
                requires_structure=bool(plan.constraints.get("requires_structure")),
            ),
            index,
            item,
        )
        for index, item in enumerate(evidence_items)
    )
    return sorted(
        ranked,
        key=lambda row: (
            -quantized_score(row[0] + _binding_quality(slot, row[2])),
            -quantized_score(row[0]),
            identity_of(row[2]).key,
        ),
    )


def _candidate_ids_for_slot(
    plan: QueryPlan,
    slot: EvidenceSlot,
    ranked: list[tuple[float, int, dict[str, Any]]],
    bound_operand_items: list[dict[str, Any]],
    used_generic_operand_ids: set[str],
    used_comparison_ids: set[str],
    used_cross_page_locators: set[tuple[str, str]],
) -> list[str]:
    segment_ids = _segment_comparison_candidate_ids(plan, slot, ranked)
    if segment_ids is not None:
        return segment_ids
    if slot.metric == "revolving credit capacity" and slot.entity.startswith("active"):
        selected: list[str] = []
        facilities: set[str] = set()
        for score, _index, item in ranked:
            if score <= 0:
                continue
            attributes = _agreement_attributes(item)
            facility = attributes["facility_identity"] or attributes["facility_type"]
            if not facility or facility in facilities:
                continue
            facilities.add(facility)
            selected.append(identity_of(item).key)
            if len(selected) >= max(1, slot.cardinality):
                break
        return selected
    candidate_ids = (
        _dimension_candidate_ids(slot, ranked, bound_operand_items)
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
        candidate_ids = _distinct_candidate_ids(
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


def _segment_comparison_candidate_ids(
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


def _existing_binding_state(
    slot: EvidenceSlot,
    evidence_by_identity: dict[str, dict[str, Any]],
    *,
    requires_structure: bool,
) -> tuple[bool, str]:
    if (
        slot.status
        not in {
            "filled",
            "retrieved_partial",
            "retrieved_unverified",
            "verified_support",
        }
        or not slot.evidence_ids
    ):
        return False, "missing_existing_binding"
    if len(slot.evidence_ids) < max(1, slot.cardinality):
        return False, "incomplete_existing_binding"
    items = [evidence_by_identity.get(evidence_id) for evidence_id in slot.evidence_ids]
    if any(item is None for item in items):
        return False, "unresolved_existing_identity"
    score_for_existing = (
        _candidate_score_for_slot
        if slot.status in {"retrieved_partial", "retrieved_unverified"}
        else score_evidence_for_slot
    )
    if any(
        score_for_existing(
            slot,
            item,
            requires_structure=requires_structure,
        )
        <= 0
        for item in items
        if item is not None
    ):
        return False, "incompatible_existing_binding"
    if slot.role == "dimension" and any(
        not _trusted_dimension_item(item) for item in items if item is not None
    ):
        return False, "incompatible_existing_binding"
    return True, ""


def _bound_slot_status(
    slot: EvidenceSlot,
    evidence_ids: tuple[str, ...],
    evidence_by_identity: dict[str, dict[str, Any]],
) -> str:
    if not evidence_ids:
        return "missing"
    if (
        slot.statement_kind == "boolean_proposition"
        and slot.required_for_verification
        and not slot.required_for_retrieval
    ):
        levels = [
            boolean_proposition_authority_level(
                slot.metric,
                evidence_by_identity[evidence_id],
            )
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_identity
        ]
        if levels and "complete" not in levels and "partial" in levels:
            return "retrieved_partial"
        return "retrieved_unverified"
    return "filled"


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


def _dimension_candidate_ids(
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
        item = _item_for_raw_id(raw_evidence_id, evidence_items)
        if item is None:
            continue
        identity = identity_of(item).key
        if identity not in selected:
            selected.append(identity)
    return selected


def _distinct_candidate_ids(
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
