from __future__ import annotations

from typing import Any

from .boolean_evidence_scope import boolean_retrieval_query
from .boolean_proposition_evidence import (
    boolean_proposition_object_identity,
    proposition_qualifier,
)
from .boolean_relations import primary_boolean_relation
from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .qasper_relation_frame import question_relation_frame
from .query_planning import ensure_request_query_plan, request_planning_question
from .route_budget import route_budget_metadata


def verifier_recovery_query(request: Any) -> str:
    question = request_planning_question(request)
    plan = ensure_request_query_plan(request)
    slot_queries = [
        str(slot.query).strip()
        for slot in plan.evidence_slots
        if slot.required_for_verification and str(slot.query).strip()
    ]
    answer_relation_required = _answer_relation_required(plan)
    semantic_query = (
        question
        if answer_relation_required
        else boolean_retrieval_query(question, second_round=True)
    )
    typed_query = " ".join(
        f"{name}:{value}"
        for name, value in verifier_recovery_frame(request).items()
        if str(value or "").strip() and str(value) not in {"none", "document"}
    )
    parts = [*slot_queries, semantic_query, typed_query]
    return " ".join(dict.fromkeys(part for part in parts if part)).strip()


def verifier_recovery_frame(request: Any) -> dict[str, str]:
    question = request_planning_question(request)
    plan = ensure_request_query_plan(request)
    if _answer_relation_required(plan):
        frame = question_relation_frame(question)
        return {
            "actor": frame.actor,
            "predicate": frame.predicate,
            "object": frame.expected_object_type,
            "object_role": frame.expected_object_role,
            "qualifier": frame.qualifier,
            "quantifier": frame.quantifier,
            "scope": frame.scope,
        }
    return {
        "actor": "current_paper",
        "predicate": primary_boolean_relation(question),
        "object": boolean_proposition_object_identity(question),
        "object_role": "proposition_object",
        "qualifier": proposition_qualifier(question),
        "quantifier": "none",
        "scope": "document",
    }


def typed_qasper_recovery_requests(
    request: Any,
    requests: list[dict[str, str]],
) -> list[dict[str, str]]:
    return typed_qasper_initial_requests(request, requests)


def typed_qasper_initial_requests(
    request: Any,
    requests: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not requests or not qasper_typed_recovery_required(request):
        return requests
    return [
        {
            **item,
            "query": typed_qasper_initial_query(
                request,
                str(item.get("query") or ""),
            ),
        }
        for item in requests
    ]


def typed_qasper_initial_query(request: Any, query: str) -> str:
    if not qasper_typed_recovery_required(request):
        return str(query or "").strip()
    values = (str(query or "").strip(), verifier_recovery_query(request))
    return " ".join(dict.fromkeys(value for value in values if value))


def quality_retry_request(request: Any) -> dict[str, str]:
    query = next(
        (
            str(value).strip()
            for value in (
                getattr(request, "retrieval_query", ""),
                request_planning_question(request),
                getattr(request, "prompt", ""),
            )
            if str(value or "").strip()
        ),
        "",
    )
    return {
        "query_id": "round2:quality_retry",
        "slot_id": "",
        "query": query,
        "modality": "auto",
    }


def qasper_typed_recovery_required(request: Any) -> bool:
    if str(getattr(request, "verification_domain", "") or "").lower() != "qasper":
        return False
    plan = ensure_request_query_plan(request)
    return any(
        slot.required_for_verification
        and str(slot.statement_kind or "").lower()
        in {"answer_relation", "boolean_proposition"}
        for slot in plan.evidence_slots
    )


def verification_slot_id(plan: Any) -> str:
    return next(
        (
            str(slot.slot_id)
            for slot in plan.evidence_slots
            if slot.required_for_verification
            and str(slot.statement_kind or "").lower()
            in {"answer_relation", "boolean_proposition"}
        ),
        "support:boolean_proposition",
    )


def typed_retrieval_recovery_trace(
    request: Any,
    initial_bundle: EvidenceBundle,
    recovered_bundle: EvidenceBundle,
    requests: list[dict[str, str]],
    retrieve_decision: Any,
) -> dict[str, Any]:
    before_ids = _bundle_evidence_ids(initial_bundle)
    after_ids = _bundle_evidence_ids(recovered_bundle)
    before_slots = _typed_slot_states(initial_bundle)
    after_slots = _typed_slot_states(recovered_bundle)
    answer_relation_required = _answer_relation_required(
        ensure_request_query_plan(request)
    )
    stop_reason = str(recovered_bundle.metadata.get("retrieval_stop_reason") or "")
    recovery_outcome = "retrieval_evidence_improved"
    if not stop_reason and before_ids == after_ids and before_slots == after_slots:
        stop_reason = "recovery_no_progress"
        recovery_outcome = "no_progress"
    elif stop_reason:
        recovery_outcome = "exhausted"
    return {
        "stage": "targeted_retrieval",
        "retrieval_recovery_attempt": 1,
        "failure_type": (
            "required_answer_relation_authority_missing"
            if answer_relation_required
            else "required_boolean_authority_missing"
        ),
        "recovery_action": "targeted_slot_retrieval",
        "recovery_frame": verifier_recovery_frame(request),
        "retrieval_queries": [str(item.get("query") or "") for item in requests],
        "missing_required_slot_ids": [
            item["slot_id"]
            for item in before_slots
            if item["status"] != "verified_support"
        ],
        "evidence_ids_before": before_ids,
        "evidence_ids_after": after_ids,
        "new_evidence_ids": [value for value in after_ids if value not in before_ids],
        "removed_evidence_ids": [
            value for value in before_ids if value not in after_ids
        ],
        "slot_states_before": before_slots,
        "slot_states_after": after_slots,
        "slot_state_changed": before_slots != after_slots,
        "retrieval_status": retrieve_decision.status,
        "recovery_outcome": recovery_outcome,
        "stop_reason": stop_reason,
        **route_budget_metadata(request),
    }


def _answer_relation_required(plan: Any) -> bool:
    return any(
        slot.required_for_verification
        and str(slot.statement_kind or "").lower() == "answer_relation"
        for slot in plan.evidence_slots
    )


def _bundle_evidence_ids(bundle: EvidenceBundle) -> list[str]:
    return list(
        dict.fromkeys(
            identity_of(item).key for item in bundle.items if identity_of(item).key
        )
    )


def _typed_slot_states(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    plan = bundle.metadata.get("query_plan")
    if not isinstance(plan, dict):
        return []
    return [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "status": str(slot.get("status") or "missing"),
            "evidence_ids": list(slot.get("evidence_ids") or []),
        }
        for slot in plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and bool(slot.get("required_for_verification"))
        and str(slot.get("statement_kind") or "").lower()
        in {"answer_relation", "boolean_proposition"}
    ]
