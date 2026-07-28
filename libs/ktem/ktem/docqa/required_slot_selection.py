from __future__ import annotations

from typing import Any

from .query_planning import QueryPlan, score_evidence_for_slot


def required_slot_shortlist(
    items: list[dict[str, Any]],
    plan: QueryPlan,
    *,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], int]:
    candidates = list(items[:candidate_limit])
    restored = 0
    required_slots = [
        slot for slot in plan.evidence_slots if slot.required_for_retrieval
    ]
    for slot in required_slots:
        if any(slot_score(plan, slot, item) > 0 for item in candidates):
            continue
        ranked_tail = sorted(
            (
                (slot_score(plan, slot, item), index, item)
                for index, item in enumerate(
                    items[candidate_limit:],
                    start=candidate_limit,
                )
            ),
            key=lambda row: (-row[0], row[1]),
        )
        match = next((item for score, _index, item in ranked_tail if score > 0), None)
        if match is None:
            continue
        removable = next(
            (
                index
                for index in range(len(candidates) - 1, -1, -1)
                if not any(
                    slot_score(plan, required_slot, candidates[index]) > 0
                    for required_slot in required_slots
                )
            ),
            None,
        )
        if removable is None:
            continue
        candidates[removable] = match
        restored += 1
    return candidates, restored


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
