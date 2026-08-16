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
from .recovery_progress import (
    semantic_progress_evidence_ids,
    semantic_progress_slot_states,
    semantic_recovery_has_progress,
)
from .route_budget import route_budget_metadata

_MAX_DOCUMENT_CONTEXT_ANCHOR_CHARS = 160
_TYPED_QUERY_PREFIXES = ("actor:", "predicate:", "object:", "object_role:")


def verifier_recovery_query(request: Any) -> str:
    question = request_planning_question(request)
    plan = ensure_request_query_plan(request)
    if _answer_relation_required(plan):
        return question
    return boolean_retrieval_query(question, second_round=True)


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
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not requests or not qasper_typed_recovery_required(request):
        return requests
    metadata = recovery_query_metadata(request)
    return [
        {
            **item,
            "query": recovery_query(request, str(item.get("query") or "")),
            "query_metadata": metadata,
        }
        for item in requests
    ]


def recovery_query(request: Any, slot_query: str) -> str:
    question = request_planning_question(request)
    semantic_query = verifier_recovery_query(request)
    document_context = _recovery_document_context(request)
    parts = (
        question,
        _without_question(str(document_context.get("text") or ""), question),
        _without_question(slot_query, question),
        _without_question(semantic_query, question),
    )
    return " ".join(dict.fromkeys(part for part in parts if part)).strip()


def initial_query_metadata() -> dict[str, str]:
    return {
        "contract_id": "initial_retrieval_query.v1",
        "query_kind": "initial",
    }


def recovery_query_metadata(request: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "contract_id": "recovery_query.v1",
        "query_kind": "recovery",
        "typed_frame": verifier_recovery_frame(request),
    }
    document_context = _recovery_document_context(request)
    if document_context:
        metadata["document_context"] = document_context
    return metadata


def _recovery_document_context(request: Any) -> dict[str, str]:
    question = request_planning_question(request)
    plan = ensure_request_query_plan(request)
    if not _answer_relation_required(plan):
        return {}
    frame = question_relation_frame(question)
    if not (
        frame.actor == "unknown"
        and not frame.predicate
        and frame.expected_object_type == "answer object"
    ):
        return {}
    selected_file_ids = {
        str(value).strip()
        for value in getattr(request, "selected_file_ids", None) or []
        if str(value).strip()
    }
    if len(selected_file_ids) > 1 or (
        not selected_file_ids
        and not str(getattr(request, "active_file_id", "") or "").strip()
    ):
        return {}
    title = _selected_document_title(request)
    if not title:
        return {}
    return {
        "kind": "selected_document_title",
        "text": title,
    }


def _selected_document_title(request: Any) -> str:
    title = " ".join(str(getattr(request, "selected_source_title", "") or "").split())
    if not title or any(prefix in title.casefold() for prefix in _TYPED_QUERY_PREFIXES):
        return ""
    return title[:_MAX_DOCUMENT_CONTEXT_ANCHOR_CHARS].rstrip()


def _without_question(value: str, question: str) -> str:
    output = str(value or "")
    target = str(question or "").strip()
    if target:
        output = output.replace(target, " ")
    return " ".join(output.split())


def quality_retry_request(request: Any) -> dict[str, Any]:
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
    before_semantic_ids = semantic_progress_evidence_ids(initial_bundle)
    after_semantic_ids = semantic_progress_evidence_ids(recovered_bundle)
    before_semantic_slots = semantic_progress_slot_states(
        initial_bundle,
        before_slots,
    )
    after_semantic_slots = semantic_progress_slot_states(
        recovered_bundle,
        after_slots,
    )
    answer_relation_required = _answer_relation_required(
        ensure_request_query_plan(request)
    )
    stop_reason = str(recovered_bundle.metadata.get("retrieval_stop_reason") or "")
    recovery_outcome = "retrieval_evidence_improved"
    if not typed_retrieval_recovery_has_progress(initial_bundle, recovered_bundle):
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
        "semantic_evidence_ids_before": before_semantic_ids,
        "semantic_evidence_ids_after": after_semantic_ids,
        "new_semantic_evidence_ids": [
            value for value in after_semantic_ids if value not in before_semantic_ids
        ],
        "removed_semantic_evidence_ids": [
            value for value in before_semantic_ids if value not in after_semantic_ids
        ],
        "slot_states_before": before_slots,
        "slot_states_after": after_slots,
        "slot_state_changed": before_slots != after_slots,
        "semantic_slot_states_before": before_semantic_slots,
        "semantic_slot_states_after": after_semantic_slots,
        "semantic_slot_state_changed": (before_semantic_slots != after_semantic_slots),
        "retrieval_status": retrieve_decision.status,
        "recovery_outcome": recovery_outcome,
        "stop_reason": stop_reason,
        **route_budget_metadata(request),
    }


def typed_retrieval_recovery_has_progress(
    initial_bundle: EvidenceBundle,
    recovered_bundle: EvidenceBundle,
) -> bool:
    return semantic_recovery_has_progress(
        initial_bundle,
        recovered_bundle,
        _typed_slot_states(initial_bundle),
        _typed_slot_states(recovered_bundle),
    )


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
