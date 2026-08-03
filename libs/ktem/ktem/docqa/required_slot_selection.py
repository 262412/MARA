from __future__ import annotations

from typing import Any

from .evidence_identity import evidence_aliases, identity_of
from .finance_query_planning import finance_metric_evidence_matches
from .finance_scale import source_scale_evidence
from .query_planning import QueryPlan, score_evidence_for_slot

REQUIRED_SLOT_CANDIDATE_QUOTA = 2
EXECUTION_SLOT_PARENT_QUOTA = 1


def required_slot_candidate_limit(
    plan: QueryPlan,
    *,
    base_limit: int,
) -> int:
    quota = sum(
        REQUIRED_SLOT_CANDIDATE_QUOTA
        + (
            EXECUTION_SLOT_PARENT_QUOTA
            if slot.required_for_execution and slot.role == "operand"
            else 0
        )
        for slot in plan.evidence_slots
        if slot_requires_selection(slot)
    )
    return max(base_limit, quota)


def required_slot_shortlist(
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], int]:
    required_slots = [
        slot for slot in plan.evidence_slots if slot_requires_selection(slot)
    ]
    if not required_slots or candidate_limit <= 0:
        return list(items[: max(0, candidate_limit)]), 0
    per_slot_quota = max(
        1,
        min(
            REQUIRED_SLOT_CANDIDATE_QUOTA,
            candidate_limit // len(required_slots),
        ),
    )
    selected_ids: set[str] = set()
    selected_locators: set[tuple[str, str]] = set()
    preserve_locator_diversity = bool(
        plan.constraints.get("requires_distinct_source_pages")
    )
    original_index = {identity_of(item).key: index for index, item in enumerate(items)}
    required_slots.sort(
        key=lambda slot: (
            sum(slot_score(plan, slot, item) > 0 for item in items),
            slot.slot_id,
        )
    )
    for slot in required_slots:
        ranked = sorted(
            (
                (slot_score(plan, slot, item), index, item)
                for index, item in enumerate(items)
            ),
            key=lambda row: (-row[0], -_reranker_score(row[2]), row[1]),
        )
        if slot.required_for_execution and slot.role == "operand":
            _add_slot_candidates(
                ranked,
                selected_ids,
                selected_locators,
                candidate_limit=candidate_limit,
                quota=per_slot_quota,
                preserve_locator_diversity=preserve_locator_diversity,
                atomic=True,
            )
            _add_slot_candidates(
                ranked,
                selected_ids,
                selected_locators,
                candidate_limit=candidate_limit,
                quota=EXECUTION_SLOT_PARENT_QUOTA,
                preserve_locator_diversity=False,
                atomic=False,
            )
        else:
            _add_slot_candidates(
                ranked,
                selected_ids,
                selected_locators,
                candidate_limit=candidate_limit,
                quota=per_slot_quota,
                preserve_locator_diversity=preserve_locator_diversity,
                atomic=None,
            )
        if len(selected_ids) >= candidate_limit:
            break
    _add_execution_dimension_candidates(
        items,
        selected_ids,
        candidate_limit=candidate_limit,
    )
    return _ordered_shortlist(
        items,
        selected_ids,
        candidate_limit=candidate_limit,
        original_index=original_index,
    )


def _ordered_shortlist(
    items: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    candidate_limit: int,
    original_index: dict[str, int],
) -> tuple[list[dict[str, Any]], int]:
    for item in items:
        if len(selected_ids) >= candidate_limit:
            break
        selected_ids.add(identity_of(item).key)
    candidates = [item for item in items if identity_of(item).key in selected_ids][
        :candidate_limit
    ]
    restored = sum(
        original_index[identity_of(item).key] >= candidate_limit for item in candidates
    )
    return candidates, restored


def _add_execution_dimension_candidates(
    items: list[dict[str, Any]],
    selected_ids: set[str],
    *,
    candidate_limit: int,
) -> None:
    operands = [
        item
        for item in items
        if identity_of(item).key in selected_ids and _is_atomic_operand_candidate(item)
    ]
    for operand in operands:
        if len(selected_ids) >= candidate_limit:
            return
        _scale, evidence_id = source_scale_evidence(operand, items)
        dimension = next(
            (
                item
                for item in items
                if evidence_id and evidence_id in evidence_aliases(item)
            ),
            None,
        )
        if dimension is not None:
            selected_ids.add(identity_of(dimension).key)


def _add_slot_candidates(
    ranked: list[tuple[float, int, dict[str, Any]]],
    selected_ids: set[str],
    selected_locators: set[tuple[str, str]],
    *,
    candidate_limit: int,
    quota: int,
    preserve_locator_diversity: bool,
    atomic: bool | None,
) -> None:
    added = 0
    for score, _index, item in ranked:
        identity = identity_of(item).key
        locator = _source_page(item)
        if atomic is not None and _is_atomic_operand_candidate(item) is not atomic:
            continue
        if (
            score <= 0
            or identity in selected_ids
            or (
                preserve_locator_diversity
                and locator[1]
                and locator in selected_locators
            )
        ):
            continue
        selected_ids.add(identity)
        if locator[1]:
            selected_locators.add(locator)
        added += 1
        if added >= quota or len(selected_ids) >= candidate_limit:
            return


def _is_atomic_operand_candidate(item: dict[str, Any]) -> bool:
    return identity_of(item).kind in {"cell", "span"} and item.get("value") not in (
        None,
        "",
    )


def slot_requires_selection(slot: Any) -> bool:
    return bool(
        slot.required_for_retrieval
        or (
            slot.required_for_verification
            and slot.statement_kind == "boolean_proposition"
        )
    )


def _reranker_score(item: dict[str, Any]) -> float:
    metadata = dict(item.get("metadata") or {})
    for field in ("reranking_score", "reranker_score"):
        value = item.get(field, metadata.get(field))
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _source_page(item: dict[str, Any]) -> tuple[str, str]:
    metadata = dict(item.get("metadata") or {})
    return (
        str(
            item.get("source_id")
            or item.get("file_id")
            or item.get("document_id")
            or metadata.get("source_id")
            or ""
        ).strip(),
        str(
            item.get("page_label")
            or item.get("page")
            or item.get("page_number")
            or metadata.get("page_label")
            or ""
        ).strip(),
    )


def slot_score(
    plan: QueryPlan,
    slot: Any,
    item: dict[str, Any],
) -> float:
    score = score_evidence_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )
    if score > 0 or not (slot.required_for_execution and slot.role == "operand"):
        return score
    if _is_atomic_operand_candidate(item):
        return 0.0
    text = " ".join(
        str(item.get(field) or "")
        for field in ("text", "caption", "ocr_text", "table_title")
    ).lower()
    metric = str(slot.metric or "").strip().lower()
    table_like = bool(
        item.get("table_id")
        or item.get("table_instance_id")
        or str(item.get("modality") or "").lower() == "table"
        or str(item.get("element_type") or "").lower() == "table"
    )
    if table_like and metric and finance_metric_evidence_matches(metric, text):
        return 0.25
    return 0.0
