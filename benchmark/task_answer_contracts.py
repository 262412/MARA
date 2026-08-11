from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from ktem.docqa.boolean_claim_verification import canonical_boolean_answer_polarity
from ktem.docqa.evidence_identity import identity_of

from .metrics import is_abstention_answer, normalize_text
from .terminal_answer_state import rebuild_terminal_answer_state

QASPER_RUNTIME_AUTHORITY_AUDIT = "qasper_runtime_authority_audit.v1"


def apply_task_answer_contract(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    llm_factory: Callable[[], Any],
) -> bool:
    """Audit QASPER runtime authority without producing a semantic answer."""

    del llm_factory
    if "qasper" not in str(dataset_name or "").lower() or prediction.get("error"):
        return False
    metadata = prediction.setdefault("evidence_metadata", {})
    existing = metadata.get("qasper_answerability")
    if isinstance(existing, dict) and existing.get("contract_id") == (
        QASPER_RUNTIME_AUTHORITY_AUDIT
    ):
        prediction["task_answer_contract"] = {
            "contract_id": QASPER_RUNTIME_AUTHORITY_AUDIT,
            "status": "already_audited",
        }
        return False

    audit = _qasper_audit_context(prediction)
    _record_qasper_audit(prediction, metadata, audit)
    if not audit["violation"] and audit["scored_label"] in {
        "yes",
        "no",
        "unanswerable",
    }:
        prediction["predicted_answer"] = audit["scored_label"]
        prediction["answer_for_scoring"] = audit["scored_label"]
        _update_contract_trace(prediction)
    return False


def _qasper_audit_context(prediction: dict[str, Any]) -> dict[str, Any]:
    projection_required = (
        str(prediction.get("answer_type") or "").strip().lower() == "boolean"
    )
    engine_answer = str(prediction.get("engine_terminal_answer") or "")
    engine_label = _canonical_semantic_label(engine_answer)
    scored_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    scored_label = _canonical_semantic_label(scored_answer)
    authority_applicable = bool(
        projection_required and ({engine_label, scored_label} & {"yes", "no"})
    )
    projection_present = _runtime_projection_present(prediction)
    authority = runtime_boolean_authority(prediction, engine_label)
    semantic_rewrite = bool(
        projection_present
        and engine_label
        and scored_label
        and engine_label != scored_label
    )
    authority_missing = bool(
        (projection_required and not projection_present)
        or (authority_applicable and not authority["complete"])
    )
    action = (
        "hard_violation_semantic_rewrite"
        if semantic_rewrite
        else "hard_violation_missing_runtime_authority"
        if authority_missing
        else "pass_through"
    )
    return {
        "engine_answer": engine_answer,
        "engine_label": engine_label,
        "scored_answer": scored_answer,
        "scored_label": scored_label,
        "authority": authority,
        "action": action,
        "projection_present": projection_present,
        "semantic_rewrite": semantic_rewrite,
        "runtime_boolean_authority_applicable": authority_applicable,
        "runtime_boolean_projection_required": projection_required,
        "violation": semantic_rewrite or authority_missing,
    }


def _record_qasper_audit(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    prediction["contract_action"] = audit["action"]
    prediction["contract_semantic_rewrite"] = audit["semantic_rewrite"]
    prediction["post_engine_answerability_llm_call_count"] = 0
    prediction["task_answer_contract"] = {
        "contract_id": QASPER_RUNTIME_AUTHORITY_AUDIT,
        "status": "violation" if audit["violation"] else "audited",
    }
    metadata["qasper_answerability"] = _answerability_trace(
        prediction,
        **{key: value for key, value in audit.items() if key != "violation"},
    )
    metadata["answerability_contract_trace"] = _contract_trace(prediction, audit)


def _contract_trace(
    prediction: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    semantic_rewrite = bool(audit["semantic_rewrite"])
    return {
        "pre_contract_answer": audit["engine_answer"],
        "post_contract_answer": audit["scored_answer"],
        "final_post_contract_answer": audit["scored_answer"],
        "product_answer": audit["engine_answer"],
        "pre_guardrail_answer": audit["engine_answer"],
        "pre_verification_answer": audit["engine_answer"],
        "candidate_for_answerability": audit["engine_answer"],
        "input_candidate_kind": "engine_terminal_answer",
        "rewrite_applied": semantic_rewrite,
        "rewrite_type": (
            _rewrite_type(audit["engine_label"], audit["scored_label"])
            if semantic_rewrite
            else "none"
        ),
        "rewrite_reason": audit["action"],
        "contract_action": audit["action"],
        "contract_semantic_rewrite": semantic_rewrite,
        "post_engine_answerability_llm_call_count": 0,
        "engine_verify_decision": deepcopy(
            prediction.get("engine_verify_decision") or {}
        ),
    }


def synchronize_terminal_answer_state(prediction: dict[str, Any]) -> bool:
    """Project the immutable engine state without rerunning verification."""

    from .finance_terminal_sync import is_finance_terminal_prediction
    from .finance_terminal_sync import (
        synchronize_terminal_answer_state as synchronize_finance,
    )

    if is_finance_terminal_prediction(prediction):
        return synchronize_finance(prediction)
    contract = prediction.get("task_answer_contract")
    if not isinstance(contract, dict) or contract.get("contract_id") != (
        QASPER_RUNTIME_AUTHORITY_AUDIT
    ):
        return False
    engine_label = _canonical_semantic_label(
        str(prediction.get("engine_terminal_answer") or "")
    )
    final_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    final_label = _canonical_semantic_label(final_answer)
    semantic_rewrite = bool(
        engine_label and final_label and engine_label != final_label
    )
    if semantic_rewrite:
        prediction["contract_semantic_rewrite"] = True
        prediction["contract_action"] = "hard_violation_semantic_rewrite"
        contract["status"] = "violation"
        _update_contract_trace(prediction)
        return True
    engine_state = prediction.get("engine_terminal_state")
    if not isinstance(engine_state, dict) or not engine_state:
        _update_contract_trace(prediction)
        return True
    verify_decision = deepcopy(prediction.get("engine_verify_decision") or {})
    guardrail_decision = deepcopy(
        prediction.get("engine_terminal_guardrail_decision") or {}
    )
    engine_bundle = prediction.get("engine_terminal_evidence_bundle")
    bundle_metadata = (
        engine_bundle.get("metadata") if isinstance(engine_bundle, dict) else None
    )
    supporting_evidence = _records(
        bundle_metadata.get("verified_claim_support_evidence")
        if isinstance(bundle_metadata, dict)
        else None
    )
    citations = [
        dict(value)
        for value in prediction.get("structured_citations") or []
        if isinstance(value, dict)
    ]
    engine_answer = str(prediction.get("engine_terminal_answer") or "")
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    terminal_answer = (
        final_label or final_answer
        if answer_type == "boolean" or is_abstention_answer(engine_answer)
        else engine_answer
    )
    rebuild_terminal_answer_state(
        prediction,
        answer=terminal_answer,
        verify_decision=verify_decision,
        claim_verification={
            "contract_id": QASPER_RUNTIME_AUTHORITY_AUDIT,
            "status": str(verify_decision.get("status") or ""),
            "claim_results": deepcopy(verify_decision.get("claim_results") or []),
            "unsupported_claims": list(verify_decision.get("unsupported_claims") or []),
            "unknown_claims": list(verify_decision.get("unknown_claims") or []),
        },
        supporting_evidence=supporting_evidence,
        guardrail_decision=guardrail_decision,
        emitted_citations=citations,
        scoring_answer=final_answer,
    )
    _update_contract_trace(prediction)
    return True


def _runtime_projection_present(prediction: dict[str, Any]) -> bool:
    state = prediction.get("engine_terminal_state")
    verify_decision = prediction.get("engine_verify_decision")
    guardrail_decision = prediction.get("engine_terminal_guardrail_decision")
    evidence_bundle = prediction.get("engine_terminal_evidence_bundle")
    terminal_answer = str(prediction.get("engine_terminal_answer") or "")
    if not (
        terminal_answer
        and isinstance(state, dict)
        and state.get("contract_id") == "engine_terminal_state.v1"
        and isinstance(verify_decision, dict)
        and isinstance(guardrail_decision, dict)
        and isinstance(evidence_bundle, dict)
    ):
        return False
    expected_state = {
        "contract_id": "engine_terminal_state.v1",
        "answer": terminal_answer,
        "verify_decision": verify_decision,
        "guardrail_decision": guardrail_decision,
        "evidence_bundle": evidence_bundle,
    }
    if state != expected_state:
        return False
    expected_hash = hashlib.sha256(
        json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return str(prediction.get("engine_terminal_projection_hash") or "") == (
        expected_hash
    )


def runtime_boolean_authority(
    prediction: dict[str, Any],
    engine_label: str = "",
) -> dict[str, Any]:
    if not engine_label:
        engine_label = _canonical_semantic_label(
            str(prediction.get("engine_terminal_answer") or "")
        )
    (
        decision,
        bundle,
        plan,
        slots,
        verified_slots,
        required_ids,
    ) = _runtime_authority_inputs(prediction)
    evidence_id = str(decision.get("authoritative_evidence_id") or "")
    quote = str(decision.get("authoritative_quote") or "")
    evidence_ref = str(decision.get("authoritative_evidence_ref") or "")
    item = _evidence_item_by_identity(_records(bundle.get("items")), evidence_id)
    quote_status = _quote_identity_status(
        item,
        quote,
        decision.get("authoritative_span_start"),
        decision.get("authoritative_span_end"),
    )
    claim_results = [
        result
        for result in decision.get("claim_results") or []
        if isinstance(result, dict)
    ]
    supported_claim = any(
        result.get("status") == "supported"
        and str(result.get("canonical_answer_polarity") or "") == engine_label
        and evidence_id in (result.get("supporting_evidence_ids") or [])
        for result in claim_results
    )
    complete = bool(
        engine_label in {"yes", "no"}
        and decision.get("status") == "supported"
        and decision.get("canonical_answer_polarity") == engine_label
        and decision.get("boolean_authority_status") == "verified_support"
        and plan.get("stage") == "verified"
        and plan.get("state_authority") == "verified_claim_support.v1"
        and slots
        and len(verified_slots) == len(slots)
        and evidence_id
        and evidence_id in required_ids
        and evidence_ref
        and quote_status == "bound"
        and supported_claim
    )
    failure_kind = _runtime_authority_failure_kind(
        decision,
        engine_label=engine_label,
        slots=slots,
        required_ids=required_ids,
        evidence_id=evidence_id,
        claim_results=claim_results,
        quote_status=quote_status,
        complete=complete,
    )
    return {
        "complete": complete,
        "status": "complete" if complete else "missing_or_inconsistent",
        "decision": decision,
        "plan": plan,
        "required_slot_ids": [str(slot.get("slot_id") or "") for slot in slots],
        "required_evidence_ids": required_ids,
        "evidence_id": evidence_id,
        "evidence_ref": evidence_ref,
        "quote": quote,
        "quote_ref_validation_status": quote_status,
        "claim_results": claim_results,
        "failure_kind": failure_kind,
    }


def _runtime_authority_inputs(
    prediction: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    decision = prediction.get("engine_verify_decision")
    decision = decision if isinstance(decision, dict) else {}
    bundle = prediction.get("engine_terminal_evidence_bundle")
    bundle = bundle if isinstance(bundle, dict) else {}
    bundle_metadata = bundle.get("metadata")
    bundle_metadata = bundle_metadata if isinstance(bundle_metadata, dict) else {}
    plan = bundle_metadata.get("query_plan") or bundle_metadata.get("bound_query_plan")
    if not isinstance(plan, dict) or not plan:
        metadata = prediction.get("evidence_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        plan = metadata.get("query_plan") or metadata.get("bound_query_plan")
    plan = plan if isinstance(plan, dict) else {}
    slots = [
        slot
        for slot in plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and slot.get("required_for_verification")
        and (
            slot.get("role") == "support"
            or slot.get("statement_kind") == "boolean_proposition"
        )
    ]
    verified_slots = [
        slot for slot in slots if slot.get("status") == "verified_support"
    ]
    required_ids = list(
        dict.fromkeys(
            str(evidence_id)
            for slot in verified_slots
            for evidence_id in slot.get("evidence_ids") or []
            if str(evidence_id).strip()
        )
    )
    return decision, bundle, plan, slots, verified_slots, required_ids


def _runtime_authority_failure_kind(
    decision: dict[str, Any],
    *,
    engine_label: str,
    slots: list[dict[str, Any]],
    required_ids: list[str],
    evidence_id: str,
    claim_results: list[dict[str, Any]],
    quote_status: str,
    complete: bool,
) -> str:
    if not slots or not required_ids or not evidence_id:
        return "authority_missing"
    if decision.get("status") != "supported" or (
        decision.get("canonical_answer_polarity") != engine_label
    ):
        return "semantic_verifier"
    claim_reasons = " ".join(
        str(result.get("reason") or "") for result in claim_results
    ).lower()
    if any(
        marker in claim_reasons
        for marker in ("scope", "cited_work", "current_paper", "quantified", "actor")
    ):
        return "scope"
    if quote_status != "bound":
        return "ref_mismatch"
    return "" if complete else "authority_missing"


def _answerability_trace(
    prediction: dict[str, Any],
    *,
    engine_answer: str,
    engine_label: str,
    scored_answer: str,
    scored_label: str,
    authority: dict[str, Any],
    action: str,
    projection_present: bool,
    semantic_rewrite: bool,
    runtime_boolean_authority_applicable: bool,
    runtime_boolean_projection_required: bool,
) -> dict[str, Any]:
    complete = bool(authority["complete"])
    failure_kind = (
        "authority_missing"
        if runtime_boolean_projection_required and not projection_present
        else ""
        if complete or not runtime_boolean_authority_applicable
        else str(authority.get("failure_kind") or "authority_missing")
    )
    return {
        "contract_id": QASPER_RUNTIME_AUTHORITY_AUDIT,
        "status": "violation" if action.startswith("hard_violation") else "ok",
        "verdict": engine_label if complete else "insufficient_evidence",
        "raw_verifier_verdict": (
            f"{engine_label}_complete"
            if complete and engine_label in {"yes", "no"}
            else ""
        ),
        "action": action,
        "reason": (
            "runtime_authority_verified"
            if complete
            else "runtime_projection_missing"
            if runtime_boolean_projection_required and not projection_present
            else "runtime_safe_abstention"
            if not runtime_boolean_authority_applicable
            else "runtime_authority_missing_or_inconsistent"
            if runtime_boolean_authority_applicable
            else "runtime_boolean_authority_not_applicable"
        ),
        "primary_answer": engine_answer,
        "adjudicated_polarity": engine_label,
        "final_post_contract_answer": scored_answer,
        "post_contract_answer": scored_answer,
        "engine_terminal_answer": engine_answer,
        "engine_semantic_label": engine_label,
        "scored_semantic_label": scored_label,
        "contract_semantic_rewrite": semantic_rewrite,
        "runtime_projection_present": projection_present,
        "runtime_boolean_authority_applicable": (runtime_boolean_authority_applicable),
        "runtime_boolean_projection_required": (runtime_boolean_projection_required),
        "runtime_authority_failure_kind": failure_kind,
        "post_engine_answerability_llm_call_count": 0,
        **_authority_trace_fields(authority, complete=complete),
        "engine_verify_decision": deepcopy(
            prediction.get("engine_verify_decision") or {}
        ),
    }


def _authority_trace_fields(
    authority: dict[str, Any],
    *,
    complete: bool,
) -> dict[str, Any]:
    slot_ids = authority["required_slot_ids"]
    evidence_ids = authority["required_evidence_ids"]
    return {
        "evidence_quote": authority["quote"],
        "evidence_ref": authority["evidence_ref"],
        "authoritative_quote_evidence_id": authority["evidence_id"],
        "quote_ref_validation_status": authority["quote_ref_validation_status"],
        "quote_grounded": str(complete).lower(),
        "quote_supports_relation": str(complete).lower(),
        "boolean_scope_valid": str(complete).lower(),
        "verifier_required_slot_ids": ",".join(slot_ids),
        "verifier_required_slot_count": str(len(slot_ids)),
        "verifier_required_slot_authority_count": str(len(slot_ids) if complete else 0),
        "verifier_required_evidence_ids": ",".join(evidence_ids),
        "verifier_missing_required_slot_ids": "" if complete else ",".join(slot_ids),
        "verifier_missing_required_evidence_ids": (
            "" if complete else ",".join(evidence_ids)
        ),
        "verifier_required_authority_status": (
            "complete" if complete else "missing_required_evidence"
        ),
        "verifier_required_evidence_coverage": ("1.000000" if complete else "0.000000"),
        "final_support_evidence_ids": list(evidence_ids),
    }


def _update_contract_trace(prediction: dict[str, Any]) -> None:
    metadata = prediction.setdefault("evidence_metadata", {})
    semantic_rewrite = bool(prediction.get("contract_semantic_rewrite"))
    final_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    trace = metadata.get("answerability_contract_trace")
    if isinstance(trace, dict):
        trace["contract_semantic_rewrite"] = semantic_rewrite
        trace["rewrite_applied"] = semantic_rewrite
        trace["contract_action"] = prediction.get("contract_action")
        trace["post_contract_answer"] = final_answer
        trace["final_post_contract_answer"] = final_answer
    authority_trace = metadata.get("qasper_answerability")
    if isinstance(authority_trace, dict):
        authority_trace["post_contract_answer"] = final_answer
        authority_trace["final_post_contract_answer"] = final_answer


def _evidence_item_by_identity(
    items: list[dict[str, Any]],
    evidence_id: str,
) -> dict[str, Any] | None:
    if not evidence_id:
        return None
    matches = []
    for item in items:
        try:
            if identity_of(item).key == evidence_id:
                matches.append(item)
        except ValueError:
            continue
    return matches[0] if len(matches) == 1 else None


def _quote_identity_status(
    item: dict[str, Any] | None,
    quote: str,
    start: Any,
    end: Any,
) -> str:
    if item is None or not quote:
        return "evidence_ref_quote_mismatch"
    text = "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )
    if text.count(quote) != 1:
        return "evidence_ref_quote_mismatch"
    if not isinstance(start, int) or not isinstance(end, int):
        return "evidence_ref_quote_mismatch"
    return "bound" if text[start:end] == quote else "evidence_ref_quote_mismatch"


def _canonical_semantic_label(value: str) -> str:
    if is_abstention_answer(str(value or "")):
        return "unanswerable"
    polarity = canonical_boolean_answer_polarity(str(value or ""))
    return polarity or normalize_text(value)


def _rewrite_type(before: str, after: str) -> str:
    if before == after:
        return "none"
    before_abstained = before == "unanswerable"
    after_abstained = after == "unanswerable"
    if before_abstained and not after_abstained:
        return "unanswerable_to_polarity"
    if not before_abstained and after_abstained:
        return "polarity_to_unanswerable"
    return "answer_rewrite"


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
