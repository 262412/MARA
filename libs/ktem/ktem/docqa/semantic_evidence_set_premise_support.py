from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .boolean_authority_schema import BooleanEvidenceAuthority


def premises_overlap(premises: list[BooleanEvidenceAuthority]) -> bool:
    for index, left in enumerate(premises):
        for right in premises[index + 1 :]:
            if left.evidence_id == right.evidence_id and max(
                left.span_start, right.span_start
            ) < min(left.span_end, right.span_end):
                return True
    return False


def required_slot_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, Mapping)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return {
        _slot_value(slot, "slot_id")
        for slot in slots
        if _slot_required(slot) and _slot_value(slot, "slot_id")
    }


def _slot_value(slot: Any, key: str) -> str:
    raw = slot.get(key) if isinstance(slot, Mapping) else getattr(slot, key, "")
    return str(raw or "").strip()


def _slot_required(slot: Any) -> bool:
    return bool(
        slot.get("required_for_verification", False)
        if isinstance(slot, Mapping)
        else getattr(slot, "required_for_verification", False)
    )


def optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
