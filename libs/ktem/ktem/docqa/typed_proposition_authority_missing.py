from __future__ import annotations

from dataclasses import replace
from typing import Any

from .query_plan_schema import QueryPlan
from .typed_proposition_authority_schema import (
    missing_authority,
    planned_answer_type,
    qasper_authority_domain,
)
from .verification_schema import VerifyDecision


def with_qasper_missing_authority(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    domain: str,
    reason: str,
) -> VerifyDecision:
    if not qasper_authority_domain(domain):
        return decision
    authority = missing_authority(
        planned_answer_type(request),
        question,
        answer,
        _required_support_slot_ids(request),
        reason,
    )
    return replace(decision, typed_authority=authority)


def with_missing_boolean_authority(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    domain: str,
    reason: str,
) -> VerifyDecision:
    """Project a typed missing state for an explicitly typed Boolean verifier."""

    if planned_answer_type(request) != "boolean":
        return with_qasper_missing_authority(
            request,
            decision,
            question=question,
            answer=answer,
            domain=domain,
            reason=reason,
        )
    authority = missing_authority(
        "boolean",
        question,
        answer,
        _required_support_slot_ids(request),
        reason,
    )
    return replace(decision, typed_authority=authority)


def _required_support_slot_ids(request: Any) -> list[str]:
    plan = getattr(request, "query_plan", None)
    if not isinstance(plan, QueryPlan):
        return []
    return [
        str(slot.slot_id)
        for slot in plan.evidence_slots
        if slot.required_for_verification and slot.role == "support"
    ]
