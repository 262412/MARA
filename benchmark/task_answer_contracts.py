from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from .qasper_answer_normalization import (
    canonical_semantic_label as _canonical_semantic_label,
)
from .qasper_answer_normalization import semantic_rewrite_type as _rewrite_type
from .qasper_answer_normalization import (
    valid_qasper_typed_label as _valid_qasper_typed_label,
)
from .qasper_runtime_authority import records as _records
from .qasper_runtime_authority import (
    runtime_authority_inputs as _runtime_authority_inputs,
)
from .qasper_runtime_authority import runtime_boolean_authority
from .qasper_runtime_projection import (
    runtime_projection_present as _runtime_projection_present,
)
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

    audit = _qasper_audit_context(prediction, dataset_name=dataset_name)
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


def _qasper_audit_context(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> dict[str, Any]:
    projection_required = _runtime_boolean_obligation(prediction)
    typed_label_required = _qasper_typed_label_required(
        prediction,
        dataset_name=dataset_name,
        boolean_obligation=projection_required,
    )
    engine_answer = str(prediction.get("engine_terminal_answer") or "")
    engine_label = _canonical_semantic_label(engine_answer)
    scored_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    scored_label = _canonical_semantic_label(scored_answer)
    authority_applicable = projection_required
    polarity_authority_required = bool(
        projection_required and ({engine_label, scored_label} & {"yes", "no"})
    )
    projection_present = _runtime_projection_present(prediction)
    authority = runtime_boolean_authority(prediction, engine_label)
    conflict_authority_required = (
        authority.get("authority_kind") == "authoritative_conflict"
    )
    semantic_rewrite = bool(
        engine_label and scored_label and engine_label != scored_label
    )
    invalid_typed_label = bool(
        typed_label_required
        and (
            not _valid_qasper_typed_label(engine_answer)
            or not _valid_qasper_typed_label(scored_answer)
        )
    )
    authority_missing = bool(
        (projection_required and not projection_present)
        or (
            (polarity_authority_required or conflict_authority_required)
            and not authority["complete"]
        )
    )
    action = (
        "hard_violation_semantic_rewrite"
        if semantic_rewrite
        else (
            "hard_violation_missing_runtime_authority"
            if authority_missing
            else (
                "hard_violation_invalid_typed_label"
                if invalid_typed_label
                else "pass_through"
            )
        )
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
        "invalid_typed_label": invalid_typed_label,
        "typed_label_required": typed_label_required,
        "runtime_boolean_authority_applicable": authority_applicable,
        "runtime_boolean_polarity_authority_required": polarity_authority_required,
        "runtime_boolean_conflict_authority_required": conflict_authority_required,
        "runtime_boolean_projection_required": projection_required,
        "violation": semantic_rewrite or authority_missing or invalid_typed_label,
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
        return _synchronize_runtime_terminal_commit(prediction)

    return _synchronize_qasper_terminal_state(prediction, contract)


def _synchronize_qasper_terminal_state(
    prediction: dict[str, Any],
    contract: dict[str, Any],
) -> bool:
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
    terminal_commit = prediction.get("engine_terminal_commit") or prediction.get(
        "terminal_semantic_commit"
    )
    immutable_engine_answer = engine_answer
    if isinstance(terminal_commit, dict) and _runtime_projection_present(prediction):
        immutable_engine_answer = str(
            terminal_commit.get("semantic_answer") or engine_answer
        )
    terminal_answer = immutable_engine_answer
    scoring_answer = immutable_engine_answer if semantic_rewrite else final_answer
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
        scoring_answer=scoring_answer,
    )
    if not semantic_rewrite:
        _update_contract_trace(prediction)
    return True


def _synchronize_runtime_terminal_commit(prediction: dict[str, Any]) -> bool:
    """Project a non-QASPER runtime commit without changing its answer."""

    from .answer_scoring_adapter import answer_for_scoring
    from .qasper_runtime_projection import (
        runtime_projection_present,
        runtime_terminal_commit,
    )
    from .terminal_answer_state import rebuild_terminal_answer_state

    commit = runtime_terminal_commit(prediction)
    if not commit or not runtime_projection_present(prediction):
        return False
    answer = str(commit.get("semantic_answer") or "")
    if not answer:
        return False
    verify_decision = deepcopy(commit.get("verify_decision") or {})
    guardrail_decision = deepcopy(commit.get("guardrail_decision") or {})
    supporting_evidence = [
        dict(item)
        for item in commit.get("authoritative_evidence") or []
        if isinstance(item, dict)
    ]
    citations = [
        dict(item)
        for item in prediction.get("structured_citations") or []
        if isinstance(item, dict)
    ]
    rebuild_terminal_answer_state(
        prediction,
        answer=answer,
        verify_decision=verify_decision,
        supporting_evidence=supporting_evidence,
        guardrail_decision=guardrail_decision,
        emitted_citations=citations,
        scoring_answer=answer_for_scoring(
            answer,
            dataset_name=str(
                prediction.get("dataset_name") or prediction.get("dataset") or ""
            ),
            preserve_semantic_answer=True,
        ),
    )
    prediction.setdefault("evidence_metadata", {})["terminal_commit_projection"] = {
        "contract_id": commit.get("contract_id"),
        "projection_hash": commit.get("projection_hash"),
        "answer": answer,
    }
    return True


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
    invalid_typed_label: bool,
    typed_label_required: bool,
    runtime_boolean_authority_applicable: bool,
    runtime_boolean_polarity_authority_required: bool,
    runtime_boolean_conflict_authority_required: bool,
    runtime_boolean_projection_required: bool,
) -> dict[str, Any]:
    complete = bool(authority["complete"])
    conflict_complete = bool(
        complete and authority.get("authority_kind") == "authoritative_conflict"
    )
    authority_required = bool(
        runtime_boolean_polarity_authority_required
        or runtime_boolean_conflict_authority_required
    )
    failure_kind = _runtime_authority_failure(
        authority,
        complete=complete,
        authority_required=authority_required,
        projection_required=runtime_boolean_projection_required,
        projection_present=projection_present,
    )
    return {
        "contract_id": QASPER_RUNTIME_AUTHORITY_AUDIT,
        "status": "violation" if action.startswith("hard_violation") else "ok",
        "verdict": engine_label if complete else "insufficient_evidence",
        "raw_verifier_verdict": _runtime_verifier_verdict(
            engine_label,
            complete=complete,
            conflict_complete=conflict_complete,
        ),
        "action": action,
        "reason": _runtime_authority_reason(
            complete=complete,
            conflict_complete=conflict_complete,
            authority_required=authority_required,
            authority_applicable=runtime_boolean_authority_applicable,
            projection_required=runtime_boolean_projection_required,
            projection_present=projection_present,
        ),
        "primary_answer": engine_answer,
        "adjudicated_polarity": "" if conflict_complete else engine_label,
        "final_post_contract_answer": scored_answer,
        "post_contract_answer": scored_answer,
        "engine_terminal_answer": engine_answer,
        "engine_semantic_label": engine_label,
        "scored_semantic_label": scored_label,
        "contract_action": action,
        "contract_semantic_rewrite": semantic_rewrite,
        "invalid_typed_label": invalid_typed_label,
        "typed_label_required": typed_label_required,
        "runtime_projection_present": projection_present,
        "runtime_boolean_authority_applicable": (runtime_boolean_authority_applicable),
        "runtime_boolean_polarity_authority_required": (
            runtime_boolean_polarity_authority_required
        ),
        "runtime_boolean_conflict_authority_required": (
            runtime_boolean_conflict_authority_required
        ),
        "runtime_boolean_projection_required": (runtime_boolean_projection_required),
        "runtime_authority_failure_kind": failure_kind,
        "post_engine_answerability_llm_call_count": 0,
        **_authority_trace_fields(authority, complete=complete),
        "engine_verify_decision": deepcopy(
            prediction.get("engine_verify_decision") or {}
        ),
    }


def _runtime_authority_failure(
    authority: dict[str, Any],
    *,
    complete: bool,
    authority_required: bool,
    projection_required: bool,
    projection_present: bool,
) -> str:
    if projection_required and not projection_present:
        return "authority_missing"
    if complete or not authority_required:
        return ""
    return str(authority.get("failure_kind") or "authority_missing")


def _runtime_verifier_verdict(
    engine_label: str,
    *,
    complete: bool,
    conflict_complete: bool,
) -> str:
    if conflict_complete:
        return "conflict_complete"
    return (
        f"{engine_label}_complete" if complete and engine_label in {"yes", "no"} else ""
    )


def _runtime_authority_reason(
    *,
    complete: bool,
    conflict_complete: bool,
    authority_required: bool,
    authority_applicable: bool,
    projection_required: bool,
    projection_present: bool,
) -> str:
    if conflict_complete:
        return "runtime_authoritative_conflict"
    if complete:
        return "runtime_authority_verified"
    if projection_required and not projection_present:
        return "runtime_projection_missing"
    if not authority_required:
        return "runtime_safe_abstention"
    if authority_applicable:
        return "runtime_authority_missing_or_inconsistent"
    return "runtime_boolean_authority_not_applicable"


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
        "authoritative_conflict": deepcopy(
            authority.get("authoritative_conflict") or {}
        ),
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


def _runtime_boolean_obligation(prediction: dict[str, Any]) -> bool:
    _decision, _bundle, plan, slots, _verified, _required = _runtime_authority_inputs(
        prediction
    )
    if str(plan.get("answer_type") or "").strip().lower() == "boolean":
        return True
    if any(
        str(slot.get("statement_kind") or "") == "boolean_proposition"
        and bool(slot.get("required_for_verification"))
        for slot in slots
    ):
        return True
    return str(prediction.get("answer_type") or "").strip().lower() == "boolean"


def _qasper_typed_label_required(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    boolean_obligation: bool,
) -> bool:
    if "qasper_typed" not in str(dataset_name or "").lower():
        return False
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    return bool(boolean_obligation or answer_type in {"boolean", "unanswerable"})
