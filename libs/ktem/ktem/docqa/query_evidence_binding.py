from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .boolean_evidence_scope import boolean_proposition_evidence_score
from .evidence_identity import identity_of
from .evidence_locators import locator_matches, locator_requirement_count
from .evidence_modality import modality_matches
from .finance_evidence_dimensions import evidence_scale
from .finance_query_planning import (
    FINANCE_METRIC_ALIASES,
    finance_metric_evidence_matches,
    finance_revenue_row_quality,
)
from .finance_scale import source_scale_evidence
from .financial_statement_identity import matches_required_financial_identity
from .query_evidence_constraints import (
    atomic_evidence,
    executable_operand_evidence,
    period_kind_conflicts,
)
from .query_evidence_text import evidence_text
from .query_phrase_extraction import source_page_locator
from .query_plan_schema import EvidenceLocator, EvidenceSlot, QueryPlan

_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_MIN_OPERAND_METRIC_COVERAGE = 0.75


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
                status="filled" if evidence_ids else "missing",
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
    return replace(plan, evidence_slots=tuple(bound_slots)), binding_trace


def _ranked_evidence(
    plan: QueryPlan,
    slot: EvidenceSlot,
    evidence_items: list[dict[str, Any]],
) -> list[tuple[float, int, dict[str, Any]]]:
    ranked = (
        (
            score_evidence_for_slot(
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
            -(row[0] + _binding_quality(slot, row[2])),
            -row[0],
            row[1],
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
    candidate_ids = (
        _dimension_candidate_ids(slot, ranked, bound_operand_items)
        if slot.role == "dimension"
        else [identity_of(item).key for score, _index, item in ranked[:3] if score > 0]
    )
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
    if slot.status != "filled" or not slot.evidence_ids:
        return False, "missing_existing_binding"
    if len(slot.evidence_ids) < max(1, slot.cardinality):
        return False, "incomplete_existing_binding"
    items = [evidence_by_identity.get(evidence_id) for evidence_id in slot.evidence_ids]
    if any(item is None for item in items):
        return False, "unresolved_existing_identity"
    if any(
        score_evidence_for_slot(
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


def _binding_quality(slot: EvidenceSlot, item: dict[str, Any]) -> float:
    quality = 0.0
    if evidence_scale(evidence_text(item), item):
        quality += 1.0
    if str(item.get("materialization_source_id") or "").strip():
        quality += 0.25
    quality += 0.5 * finance_revenue_row_quality(
        slot.metric,
        str(item.get("row_label") or ""),
    )
    return quality


def score_evidence_for_slot(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool = False,
) -> float:
    text = " ".join(
        str(value or "")
        for value in (
            evidence_text(item),
            item.get("row_label"),
            item.get("column_label"),
            item.get("period"),
            item.get("value"),
        )
        if str(value or "").strip()
    ).lower()
    locator_score = _locator_score(slot.locator, item)
    if locator_score is None:
        return 0.0
    if slot.role == "dimension":
        detected_scale = evidence_scale(text, item)
        if not detected_scale or (slot.scale and slot.scale != detected_scale):
            return 0.0
        return 2.0
    if slot.period and slot.period not in text:
        return 0.0
    if slot.period_kind and period_kind_conflicts(slot.period_kind, item, text):
        return 0.0
    if slot.role == "operand" and requires_structure and not atomic_evidence(item):
        return 0.0
    if (
        slot.statement_kind != "boolean_proposition"
        and not matches_required_financial_identity(
            item,
            slot.statement_kind,
            slot.financial_scope,
        )
    ):
        return 0.0
    boolean_score = _boolean_score(slot, item)
    if slot.statement_kind == "boolean_proposition" and boolean_score <= 0:
        return 0.0
    if not _finance_operand_matches(slot, item, text):
        return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if not modality_matches(slot.modality, modality):
        return 0.0
    return _slot_score(slot, text, modality, locator_score, boolean_score)


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


def _boolean_score(slot: EvidenceSlot, item: dict[str, Any]) -> float:
    if slot.statement_kind != "boolean_proposition":
        return 0.0
    return boolean_proposition_evidence_score(slot.metric, item)


def _finance_operand_matches(
    slot: EvidenceSlot,
    item: dict[str, Any],
    text: str,
) -> bool:
    if slot.metric not in FINANCE_METRIC_ALIASES:
        return True
    if slot.required_for_execution and not executable_operand_evidence(item):
        return False
    if not atomic_evidence(item):
        return False
    metric_text = " ".join(
        value
        for value in (
            text,
            str(item.get("row_label") or "").lower(),
            str(item.get("caption") or "").lower(),
        )
        if value
    )
    if slot.metric in {"net sales", "revenue"} and not finance_revenue_row_quality(
        slot.metric,
        str(item.get("row_label") or ""),
    ):
        return False
    if not finance_metric_evidence_matches(slot.metric, metric_text):
        return False
    observed_period = str(item.get("period") or item.get("column_label") or "").strip()
    return (not slot.period or observed_period == slot.period) and item.get(
        "value"
    ) not in (None, "")


def _slot_score(
    slot: EvidenceSlot,
    text: str,
    modality: str,
    locator_score: float,
    boolean_score: float,
) -> float:
    text_tokens = _tokens(text)
    metric_token_sets = [
        _tokens(alias)
        for alias in FINANCE_METRIC_ALIASES.get(slot.metric, (slot.metric,))
        if alias
    ]
    metric_coverage = _metric_coverage(metric_token_sets, text_tokens)
    if (
        slot.role == "operand"
        and slot.metric
        and metric_coverage < _MIN_OPERAND_METRIC_COVERAGE
    ):
        return 0.0
    score = locator_score + boolean_score + metric_coverage
    if slot.modality not in {"", "auto"} and (
        locator_score > 0 or metric_coverage > 0 or slot.modality.lower() == modality
    ):
        score += 0.25
    score += 1.0 if slot.period else 0.0
    score += 0.5 if slot.entity and slot.entity.lower() in text else 0.0
    score += 0.5 if slot.unit and slot.unit.lower() in text else 0.0
    score += (
        0.25 if modality in {"table", "formula"} and slot.role == "operand" else 0.0
    )
    return score


def _locator_score(
    locator: EvidenceLocator | None,
    item: dict[str, Any],
) -> float | None:
    if locator is None or not locator.as_dict():
        return 0.0
    if not locator_matches(
        item,
        source_id=locator.source_id,
        page_label=locator.page_label,
        page_labels=locator.page_labels,
        element_id=locator.element_id,
        figure_label=locator.figure_label,
        table_label=locator.table_label,
    ):
        return None
    return float(
        locator_requirement_count(
            source_id=locator.source_id,
            page_label=locator.page_label,
            page_labels=locator.page_labels,
            element_id=locator.element_id,
            figure_label=locator.figure_label,
            table_label=locator.table_label,
        )
    )


def _metric_coverage(
    metric_token_sets: list[set[str]],
    text_tokens: set[str],
) -> float:
    coverages = [
        len(metric_tokens & text_tokens) / len(metric_tokens)
        for metric_tokens in metric_token_sets
        if metric_tokens
    ]
    return max(coverages, default=0.0)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _trusted_dimension_item(item: dict[str, Any]) -> bool:
    scale, raw_evidence_id = source_scale_evidence(item, [item])
    return bool(scale and _item_for_raw_id(raw_evidence_id, [item]) is item)


def _item_for_raw_id(
    raw_evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    target = str(raw_evidence_id or "").strip()
    if not target:
        return None
    for item in evidence_items:
        aliases = {
            str(item.get(field) or "").strip()
            for field in ("evidence_id", "element_id", "canonical_id", "cell_id")
            if str(item.get(field) or "").strip()
        }
        if target in aliases:
            return item
    return None
