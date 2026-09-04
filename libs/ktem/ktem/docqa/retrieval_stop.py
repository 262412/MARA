from __future__ import annotations

from typing import Any


def static_retrieval_outcome(route: str) -> tuple[str, str, bool] | None:
    if route == "direct":
        return "not_required", "Direct route does not require retrieval.", False
    if route == "abstain":
        return "poor", "Route abstained before retrieval.", False
    return None


def record_missing_slot_stop(
    evidence_metadata: dict[str, Any],
    *,
    attempted_retry: bool,
) -> str:
    if not attempted_retry:
        return ""
    stop_reason = "max_retrieval_rounds_exhausted"
    evidence_metadata["retrieval_stop_reason"] = stop_reason
    evidence_metadata["missing_required_slot_ids"] = _missing_required_slot_ids(
        evidence_metadata
    )
    return stop_reason


def _missing_required_slot_ids(evidence_metadata: dict[str, Any]) -> list[str]:
    for key in ("bound_query_plan", "query_plan"):
        plan = evidence_metadata.get(key)
        if not isinstance(plan, dict):
            continue
        return [
            str(slot.get("slot_id") or "")
            for slot in plan.get("evidence_slots") or []
            if isinstance(slot, dict)
            and str(slot.get("status") or "missing") == "missing"
            and (
                bool(slot.get("required_for_retrieval"))
                or bool(slot.get("required_for_verification"))
            )
        ]
    return []
