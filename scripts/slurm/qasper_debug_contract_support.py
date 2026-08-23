from __future__ import annotations

from typing import Any


_QASPER_CANDIDATE_GENERATION_CONTRACT = "qasper_typed_candidate_generation.v2"
_SEMANTIC_VERIFIER_RUNTIME_CONTRACT = "semantic_proposition_verifier_runtime.v3"
_SEMANTIC_DEBUG_TRACE_CONTRACT = "semantic_proposition_debug_trace.v3"
_SEMANTIC_PROPOSITION_VERDICT_CONTRACT = "semantic_proposition_verdict.v4"
_SEMANTIC_ENTAILMENT_AUDIT_CONTRACT = "semantic_entailment_audit.v3"
_CONCLUSION_AUDIT_CONTRACT = "conclusion_audit.v2"
_CANDIDATE_VERIFIER_AUDIT_CONTRACT = "candidate_verifier_audit.v2"
_QASPER_CANDIDATE_MAX_RESPONSE_CHARS = 16_000


def claim_aggregation_complete(prediction: dict[str, Any]) -> bool:
    events = [
        event
        for event in prediction.get("controller_trace") or []
        if isinstance(event, dict) and event.get("stage") == "claim_aggregation"
    ]
    return bool(
        events
        and all(
            event.get("input_digest")
            and event.get("output_digest")
            and "input_text" in event
            and "output_text" in event
            for event in events
        )
    )


def terminal_metadata(prediction: dict[str, Any]) -> dict[str, Any]:
    bundle = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    metadata = _mapping(bundle.get("metadata"))
    return metadata or _mapping(prediction.get("evidence_metadata"))


def terminal_semantic_answer(prediction: dict[str, Any]) -> str:
    commit = _mapping(prediction.get("terminal_semantic_commit"))
    return (
        str(
            commit.get("semantic_answer")
            or prediction.get("engine_terminal_answer")
            or ""
        )
        .strip()
        .casefold()
    )

def _annotation_scores_complete(prediction: dict[str, Any]) -> bool:
    annotations = prediction.get("qasper_annotation_scores")
    annotations = annotations if isinstance(annotations, list) else []
    expected = _mapping(prediction.get("example_metadata")).get(
        "qasper_answer_annotations"
    )
    expected = expected if isinstance(expected, list) else []
    diagnostics = _mapping(prediction.get("qasper_annotation_diagnostics"))
    required_score_fields = {
        "annotation_index",
        "answer_f1",
        "typed_accuracy",
        "evidence_f1",
        "ambiguity_marker",
    }
    scores_complete = bool(annotations) and all(
        isinstance(score, dict)
        and score.get("contract_id") == "qasper_annotation_score.v1"
        and required_score_fields <= set(score)
        for score in annotations
    )
    diagnostics_complete = bool(
        diagnostics.get("contract_id") == "qasper_annotation_diagnostics.v1"
        and diagnostics.get("annotation_count") == len(expected)
        and isinstance(diagnostics.get("ambiguous"), bool)
        and isinstance(diagnostics.get("ambiguity_reasons"), list)
        and isinstance(diagnostics.get("canonical_answer_classes"), list)
    )
    return (
        scores_complete and diagnostics_complete and len(annotations) == len(expected)
    )


def _candidate_transform_complete(generator: dict[str, Any]) -> bool:
    stages = generator.get("transformation_stages")
    stages = stages if isinstance(stages, list) else []
    by_name = {
        str(stage.get("stage") or ""): stage
        for stage in stages
        if isinstance(stage, dict)
    }
    required = ("raw_response", "cleaning", "typed_candidate")
    if any(name not in by_name for name in required):
        return False
    common_fields = {"value", "digest", "failure_reason"}
    return bool(
        all(common_fields <= set(by_name[name]) for name in required)
        and "changed" in by_name["cleaning"]
        and by_name["typed_candidate"].get("source_stage") == "cleaning"
        and by_name["typed_candidate"].get("identity_preserved") is True
    )


def _candidate_proposition_binding_complete(generator: dict[str, Any]) -> bool:
    proposition = _mapping(generator.get("typed_proposition"))
    resolution = _mapping(generator.get("question_proposition_resolution"))
    slots = generator.get("required_slots")
    slots = slots if isinstance(slots, list) else []
    proposition_fields = ("actor", "predicate", "object_surface", "quantifier")
    return bool(
        all(str(proposition.get(field) or "").strip() for field in proposition_fields)
        and resolution.get("status") in {"complete", "repaired"}
        and slots
        and all(_candidate_slot_binding_complete(slot) for slot in slots)
    )


def _candidate_slot_binding_complete(slot: Any) -> bool:
    if not isinstance(slot, dict) or not str(slot.get("slot_id") or "").strip():
        return False
    status = slot.get("binding_status")
    evidence_ids = slot.get("evidence_ids")
    evidence_refs = slot.get("evidence_refs")
    if not isinstance(evidence_ids, list) or not isinstance(evidence_refs, list):
        return False
    if status == "bound":
        return bool(evidence_ids and evidence_refs)
    return status == "missing" and not evidence_ids and not evidence_refs


def _semantic_debug_complete(verifier: dict[str, Any]) -> bool:
    debug = _mapping(verifier.get("debug_trace"))
    if debug.get("contract_id") != _SEMANTIC_DEBUG_TRACE_CONTRACT:
        return False
    transactions = [
        event
        for event in debug.get("events") or []
        if isinstance(event, dict) and event.get("event") == "model_transaction"
    ]
    if not transactions:
        return False
    transaction = _mapping(transactions[-1].get("transaction"))
    proposal = _mapping(transaction.get("proposal"))
    audit = _mapping(transaction.get("audit"))
    if not _semantic_stage_complete(proposal, allow_not_run=False):
        return False
    return _semantic_stage_complete(audit, allow_not_run=False)


def _semantic_stage_complete(stage: dict[str, Any], *, allow_not_run: bool) -> bool:
    if allow_not_run and stage.get("status") == "not_run":
        return True
    attempts = stage.get("attempts")
    attempts = attempts if isinstance(attempts, list) else []
    required_fields = {
        "attempt",
        "attempt_id",
        "raw_response",
        "finish_reason",
        "parse_failure_reason",
        "provider_failure_reason",
    }
    return bool(
        attempts
        and all(
            isinstance(attempt, dict)
            and required_fields <= set(attempt)
            and _audit_attempt_artifact_observed(attempt)
            for attempt in attempts
        )
    )


def _transaction_identity_complete(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    return bool(
        generator.get("trace_group_id")
        and generator.get("trace_group_id") == verifier.get("trace_group_id")
        and generator.get("transaction_id")
        and generator.get("attempt_id")
        and verifier.get("transaction_id")
        and verifier.get("attempt_id")
    )


def _input_output_digests_complete(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    return bool(
        generator.get("input_digest")
        and generator.get("output_digest")
        and verifier.get("input_digest")
        and verifier.get("output_digest")
    )


def _live_models_observed(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    generator_observed = not generator or bool(generator.get("model"))
    return bool(
        generator_observed
        and verifier.get("model")
        and int(verifier.get("proposal_model_call_count") or 0) > 0
        and _candidate_bound_auditor_attempt_observed(verifier)
    )


def _candidate_bound_auditor_observed(verifier: dict[str, Any]) -> bool:
    """Compatibility alias for callers that mean an observed audit attempt."""

    return _candidate_bound_auditor_attempt_observed(verifier)


def _candidate_bound_auditor_attempt_observed(verifier: dict[str, Any]) -> bool:
    audit = _mapping(verifier.get("candidate_verification_audit"))
    mode = str(audit.get("mode") or "")
    if audit.get("status") not in {"passed", "failed"}:
        return False
    stage = _semantic_debug_audit_stage(verifier)
    attempts = stage.get("attempts")
    if not isinstance(attempts, list) or not any(
        _audit_attempt_artifact_observed(attempt)
        for attempt in attempts
        if isinstance(attempt, dict)
    ):
        return False
    return bool(
        int(verifier.get("audit_model_call_count") or 0) > 0
        and verifier.get("auditor_attempt_id")
        and mode
        and mode != "deterministic_schema_audit"
        and audit.get("audited_candidate") == verifier.get("candidate_label")
        and audit.get("audited_judgment")
        == verifier.get("candidate_verification_status")
        and audit.get("replacement_candidate_allowed") is False
    )


def _candidate_bound_auditor_passed(verifier: dict[str, Any]) -> bool:
    audit = _mapping(verifier.get("candidate_verification_audit"))
    return audit.get("status") == "passed" and _candidate_bound_auditor_attempt_observed(
        verifier
    )


def _semantic_debug_audit_stage(verifier: dict[str, Any]) -> dict[str, Any]:
    debug = _mapping(verifier.get("debug_trace"))
    events = debug.get("events")
    events = events if isinstance(events, list) else []
    transactions = [
        event
        for event in events
        if isinstance(event, dict) and event.get("event") == "model_transaction"
    ]
    if not transactions:
        return {}
    transaction = _mapping(transactions[-1].get("transaction"))
    return _mapping(transaction.get("audit"))


def _audit_attempt_artifact_observed(attempt: dict[str, Any]) -> bool:
    return bool(
        str(attempt.get("attempt_id") or "").strip()
        and (
            bool(str(attempt.get("raw_response") or ""))
            or bool(_mapping(attempt.get("parsed_value")))
        )
    )


def _failed_auditor_safe_abstention(
    verifier: dict[str, Any],
    prediction: dict[str, Any],
) -> bool:
    audit = _mapping(verifier.get("candidate_verification_audit"))
    if audit.get("status") != "failed":
        return False
    if not _candidate_bound_auditor_attempt_observed(verifier):
        return False
    if terminal_semantic_answer(prediction) != "unanswerable":
        return False
    commit = _mapping(prediction.get("terminal_semantic_commit"))
    outcome = str(
        commit.get("outcome")
        or prediction.get("terminal_outcome")
        or ""
    ).strip()
    if outcome != "safe_abstention":
        return False
    metadata = terminal_metadata(prediction)
    authority = _mapping(metadata.get("semantic_proposition_authority"))
    authority.update(_mapping(verifier.get("typed_authority")))
    return str(authority.get("state") or "") not in {
        "verified_support",
        "verified_conflict",
    }

def _empty_coverage_counts() -> dict[str, int]:
    return {
        "generator_trace": 0,
        "raw_response": 0,
        "raw_candidate_identity": 0,
        "finish_reason": 0,
        "typed_candidate_transform": 0,
        "proposition_slot_binding": 0,
        "claim_aggregation_before_after": 0,
        "per_annotation_scores": 0,
        "transaction_attempt_identity": 0,
        "effective_seed": 0,
        "input_output_digest": 0,
        "auditor_attempt_observed": 0,
        "candidate_verifier_audit": 0,
        "auditor_failed_safe_abstention": 0,
        "semantic_verifier_debug": 0,
        "live_model": 0,
    }

def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _require(violations: list[str], condition: bool, violation: str) -> None:
    if not condition:
        violations.append(violation)


_GENERATOR_REQUIRED_FIELDS = (
    "message_stack",
    "raw_response",
    "raw_response_digest",
    "provider_output_digest",
    "raw_response_truncated",
    "cleaned_response",
    "raw_candidate",
    "raw_candidate_digest",
    "typed_candidate",
    "typed_candidate_digest",
    "raw_candidate_identity_preserved",
    "finish_reason",
    "transformation_stages",
    "trace_group_id",
    "transaction_id",
    "attempt_id",
    "effective_seed",
    "input_digest",
    "output_digest",
)

_VERIFIER_REQUIRED_FIELDS = (
    "candidate_label",
    "candidate_verification_status",
    "candidate_verification_audit",
    "raw_candidate_digest",
    "typed_candidate_digest",
    "verifier_input_candidate_digest",
    "candidate_raw_identity_preserved",
    "trace_group_id",
    "transaction_id",
    "attempt_id",
    "auditor_attempt_id",
    "effective_seed",
    "input_digest",
    "output_digest",
)
