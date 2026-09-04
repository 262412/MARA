from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS


def parse_unknown_assessment(
    value: Any,
    selector_lookup: dict[str, dict[str, Any]],
    *,
    applicable_proposition_slots: set[str],
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(value, dict) or set(value) != {
        "reviewed_span_selectors",
        "unresolved_proposition_slots",
        "support_gap",
        "contradiction_gap",
    }:
        return None, "unknown_assessment_schema_invalid"
    selectors = value.get("reviewed_span_selectors")
    unresolved = _unresolved_proposition_slots(
        value.get("unresolved_proposition_slots")
    )
    support_gap = str(value.get("support_gap") or "").strip()
    contradiction_gap = str(value.get("contradiction_gap") or "").strip()
    if (
        not isinstance(selectors, list)
        or not selectors
        or len(selectors) > 12
        or len(set(selectors)) != len(selectors)
        or any(selector not in selector_lookup for selector in selectors)
    ):
        return None, "unknown_assessment_evidence_invalid"
    if (
        not unresolved
        or len(set(unresolved)) != len(unresolved)
        or any(slot not in applicable_proposition_slots for slot in unresolved)
    ):
        return None, "unknown_assessment_slot_invalid"
    if (
        not support_gap
        or not contradiction_gap
        or len(support_gap) > 320
        or len(contradiction_gap) > 320
    ):
        return None, "unknown_assessment_gap_invalid"
    reviewed = [
        {
            "span_selector": selector,
            "evidence_id": str(selector_lookup[selector]["evidence_id"]),
            "quote": str(selector_lookup[selector]["text"]),
            "span_start": int(selector_lookup[selector]["span_start"]),
            "span_end": int(selector_lookup[selector]["span_end"]),
        }
        for selector in selectors
    ]
    return {
        "reviewed_span_selectors": list(selectors),
        "reviewed_evidence": reviewed,
        "unresolved_proposition_slots": list(unresolved),
        "support_gap": support_gap,
        "contradiction_gap": contradiction_gap,
    }, ""


def _unresolved_proposition_slots(value: Any) -> list[str]:
    if isinstance(value, str):
        slots = value.split("|")
        canonical = [slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot in set(slots)]
        return slots if slots == canonical and "|".join(slots) == value else []
    if isinstance(value, list):
        return value
    return []
