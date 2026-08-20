from __future__ import annotations

from .query_plan_schema import EvidenceSlot, QueryPlan, slot_binding_state


def slot_needs_second_round(
    slot: EvidenceSlot,
    *,
    verification_domain: str = "",
) -> bool:
    if slot.required_for_retrieval and slot_binding_state(slot) != "filled":
        return True
    return bool(
        (verification_domain == "qasper" or verification_domain.startswith("qasper_"))
        and slot.statement_kind == "boolean_proposition"
        and slot.required_for_verification
        and not slot.required_for_retrieval
        and slot.status == "missing"
    )


def retrieval_budget(plan: QueryPlan) -> dict[str, int]:
    if plan.question_type in {
        "multi_period_numeric",
        "numeric",
        "cross_page",
        "visual_time_series",
    }:
        required_count = sum(
            slot.required_for_retrieval for slot in plan.evidence_slots
        )
        return {"max_items": max(16, 2 * required_count), "max_pages": 6}
    if plan.question_type == "visual":
        return {"max_items": 8, "max_pages": 6}
    if plan.question_type == "long_form":
        return {"max_items": 12, "max_pages": 5}
    return {"max_items": 8, "max_pages": 3}
