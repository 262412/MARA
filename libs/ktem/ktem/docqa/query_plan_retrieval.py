from __future__ import annotations

from .query_plan_schema import EvidenceSlot


def slot_needs_second_round(
    slot: EvidenceSlot,
    *,
    verification_domain: str = "",
) -> bool:
    if slot.required_for_retrieval and slot.status != "filled":
        return True
    return bool(
        (verification_domain == "qasper" or verification_domain.startswith("qasper_"))
        and slot.statement_kind == "boolean_proposition"
        and slot.required_for_verification
        and not slot.required_for_retrieval
        and slot.status == "missing"
    )
