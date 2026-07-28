from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .query_planning import QueryPlan
from .required_slot_selection import slot_score


def marginal_set_gain(
    item: dict[str, Any],
    selected: list[dict[str, Any]],
    plan: QueryPlan,
) -> float:
    covered_slots = {
        slot.slot_id
        for slot in plan.evidence_slots
        if any(slot_score(plan, slot, selected_item) > 0 for selected_item in selected)
    }
    slot_gain = sum(
        slot.slot_id not in covered_slots and slot_score(plan, slot, item) > 0
        for slot in plan.evidence_slots
    )
    structure_gain = float(_shares_structure_edge(item, selected))
    contrast_gain = float(
        bool(selected)
        and (
            _page(item) not in _pages(selected)
            or str(item.get("modality") or "")
            not in {str(other.get("modality") or "") for other in selected}
        )
    )
    return 1.25 * slot_gain + 0.35 * structure_gain + 0.2 * contrast_gain


def _shares_structure_edge(
    item: dict[str, Any],
    selected: list[dict[str, Any]],
) -> bool:
    continuation_id = str(item.get("continuation_id") or "")
    parent_id = str(item.get("parent_element_id") or "")
    neighbors = set(_string_values(item.get("neighbor_element_ids")))
    return any(
        (continuation_id and continuation_id == str(other.get("continuation_id") or ""))
        or (parent_id and parent_id == str(other.get("parent_element_id") or ""))
        or identity_of(other).key in neighbors
        or identity_of(item).key
        in set(_string_values(other.get("neighbor_element_ids")))
        for other in selected
    )


def _pages(items: list[dict[str, Any]]) -> set[str]:
    return {_page(item) for item in items if _page(item)}


def _page(item: dict[str, Any]) -> str:
    return str(item.get("page_label") or item.get("page") or "")


def _string_values(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(item).strip() for item in values if str(item or "").strip()]
