from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .query_planning import QueryPlan, score_evidence_for_slot

REQUIRED_SLOT_CANDIDATE_QUOTA = 2


def required_slot_candidate_limit(
    plan: QueryPlan,
    *,
    base_limit: int,
) -> int:
    required_count = sum(slot.required_for_retrieval for slot in plan.evidence_slots)
    return max(base_limit, REQUIRED_SLOT_CANDIDATE_QUOTA * required_count)


def required_slot_shortlist(
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], int]:
    required_slots = [
        slot for slot in plan.evidence_slots if slot.required_for_retrieval
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
            key=lambda row: (-row[0], row[1]),
        )
        added = 0
        for score, _index, item in ranked:
            identity = identity_of(item).key
            locator = _source_page(item)
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
            if added >= per_slot_quota or len(selected_ids) >= candidate_limit:
                break
        if len(selected_ids) >= candidate_limit:
            break
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
    return score_evidence_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )
