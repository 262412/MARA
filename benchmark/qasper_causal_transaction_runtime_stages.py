from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present

from benchmark.citation_stage_projection import citation_trace_projection_fields
from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256
from benchmark.qasper_causal_evidence_chain_utils import mapping as _mapping
from benchmark.qasper_causal_transaction_recovery import recovery_stage_payload
from benchmark.qasper_runtime_projection import runtime_projection_present
from benchmark.terminal_outcome_contract import terminal_outcome_record


def runtime_transaction_stage_payloads(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    event: Mapping[str, Any],
    transaction: Mapping[str, Any],
    proposal: Mapping[str, Any],
    audit: Mapping[str, Any],
    run_context: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "model_response_and_parser": _model_response_payload(
            generator,
            verifier,
            event,
            transaction,
            proposal,
            audit,
        ),
        "verifier_and_auditor": _verifier_auditor_payload(event, transaction, verifier),
        "recovery_state": recovery_stage_payload(prediction, verifier),
        "finalizer_and_scorer": _finalizer_scorer_payload(prediction),
        "run_provenance_and_artifact": _provenance_payload(
            prediction, generator, verifier, run_context
        ),
    }


def _model_response_payload(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    event: Mapping[str, Any],
    transaction: Mapping[str, Any],
    proposal: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = {
        "status": str(generator.get("status") or ""),
        "raw_response": str(generator.get("raw_response") or ""),
        "raw_response_digest": str(generator.get("raw_response_digest") or ""),
        "raw_response_truncated": generator.get("raw_response_truncated") is True,
        "cleaned_response": str(generator.get("cleaned_response") or ""),
        "typed_candidate": str(generator.get("typed_candidate") or ""),
        "parse_failure_reason": str(generator.get("failure_reason") or ""),
        "attempts": _candidate_response_attempts(generator),
    }
    reasons = []
    if not candidate["raw_response"] and not candidate["parse_failure_reason"]:
        reasons.append("candidate_raw_response_missing")
    if candidate["raw_response_truncated"]:
        reasons.append("candidate_raw_response_truncated")
    response_replay = _mapping(generator.get("candidate_response_replay"))
    if response_replay and response_replay.get("status") != "matched":
        reasons.extend(str(reason) for reason in response_replay.get("reasons") or [])
    semantic_replay = _mapping(verifier.get("semantic_response_replay"))
    if semantic_replay and semantic_replay.get("status") != "matched":
        reasons.extend(str(reason) for reason in semantic_replay.get("reasons") or [])
    reasons.extend(
        _attempt_response_reasons(
            "proposal",
            proposal,
            allow_not_run=_typed_proposal_not_run(
                verifier,
                event,
                transaction,
            ),
        )
    )
    reasons.extend(_attempt_response_reasons("audit", audit, allow_not_run=True))
    return _payload(
        reasons,
        candidate_generation=candidate,
        semantic_proposal=deepcopy(dict(proposal)),
        semantic_audit=deepcopy(dict(audit)),
    )


def _candidate_response_attempts(
    generator: Mapping[str, Any],
) -> list[dict[str, Any]]:
    attempts = [
        _mapping(attempt)
        for attempt in generator.get("attempts") or []
        if isinstance(attempt, Mapping)
    ]
    return [
        {
            "attempt_id": str(attempt.get("attempt_id") or ""),
            "status": str(attempt.get("status") or ""),
            "failure_reason": str(attempt.get("failure_reason") or ""),
            "failure_detail": str(attempt.get("failure_detail") or ""),
            "provider_failure_reason": str(
                attempt.get("provider_failure_reason") or ""
            ),
            "provider_failure_detail": str(
                attempt.get("provider_failure_detail") or ""
            ),
            "parse_failure_reason": str(attempt.get("parse_failure_reason") or ""),
            "raw_response": str(attempt.get("raw_response") or ""),
            "raw_response_truncated": (attempt.get("raw_response_truncated") is True),
            "cleaned_response": str(attempt.get("cleaned_response") or ""),
            "raw_candidate": str(attempt.get("raw_candidate") or ""),
            "raw_candidate_digest": str(attempt.get("raw_candidate_digest") or ""),
            "typed_candidate": str(attempt.get("typed_candidate") or ""),
            "typed_candidate_digest": str(attempt.get("typed_candidate_digest") or ""),
            "parsed_value": deepcopy(attempt.get("parsed_value")),
            "raw_candidate_identity_preserved": (
                attempt.get("raw_candidate_identity_preserved") is True
            ),
            "requested_controlled_candidate": str(
                attempt.get("requested_controlled_candidate") or ""
            ),
            "provider_raw_candidate": str(attempt.get("provider_raw_candidate") or ""),
            "cleaned_candidate": str(attempt.get("cleaned_candidate") or ""),
            "verifier_input_candidate": str(
                attempt.get("verifier_input_candidate") or ""
            ),
            "verifier_input_candidate_digest": str(
                attempt.get("verifier_input_candidate_digest") or ""
            ),
            "candidate_transport_identity_preserved": (
                attempt.get("candidate_transport_identity_preserved") is True
            ),
            "candidate_transport_status": str(
                attempt.get("candidate_transport_status") or ""
            ),
            "verifier_execution_status": str(
                attempt.get("verifier_execution_status") or ""
            ),
            "auditor_execution_status": str(
                attempt.get("auditor_execution_status") or ""
            ),
            "verifier_transport_status": str(
                attempt.get("verifier_transport_status") or ""
            ),
            "auditor_transport_status": str(
                attempt.get("auditor_transport_status") or ""
            ),
            "finish_reason": str(attempt.get("finish_reason") or ""),
            "completion_tokens": attempt.get("completion_tokens"),
            "actual_input_tokens": attempt.get("actual_input_tokens"),
            "actual_input_token_count": attempt.get("actual_input_token_count"),
            "output_digest": str(attempt.get("output_digest") or ""),
            "input_digest": str(attempt.get("input_digest") or ""),
        }
        for attempt in attempts
    ]


def _typed_proposal_not_run(
    verifier: Mapping[str, Any],
    event: Mapping[str, Any],
    transaction: Mapping[str, Any],
) -> bool:
    if transaction:
        return False
    verifier_status = str(verifier.get("status") or "")
    proposal_status = str(verifier.get("proposal_status") or "")
    if (
        verifier_status == "not_run_after_candidate_response_replay"
        and proposal_status == "not_started"
    ):
        return True
    outcome = _mapping(event.get("outcome"))
    reason = str(verifier.get("reason") or "")
    return bool(
        verifier_status == "failed"
        and verifier.get("candidate_verification_status") == "pre_audit_failed"
        and verifier.get("audit_status") == "not_started"
        and reason
        and outcome.get("status") == "failed"
        and outcome.get("reason") == reason
    )


def _verifier_auditor_payload(
    event: Mapping[str, Any],
    transaction: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    proposal_input = deepcopy(_mapping(transaction.get("proposal_input")))
    audit_input = deepcopy(_mapping(transaction.get("audit_input")))
    proposal_output = deepcopy(_mapping(transaction.get("proposal")))
    audit_output = deepcopy(_mapping(transaction.get("audit")))
    typed_pre_audit_stop = _typed_proposal_not_run(verifier, event, transaction)
    reasons = []
    if not proposal_input and not typed_pre_audit_stop:
        reasons.append("verifier_input_missing")
    elif canonical_digest(proposal_input) != transaction.get("proposal_input_digest"):
        if proposal_input:
            reasons.append("verifier_input_digest_mismatch")
    audit_ran = bool(audit_output.get("attempts"))
    if audit_ran and not audit_input:
        reasons.append("auditor_input_missing")
    elif audit_input and canonical_digest(audit_input) != transaction.get(
        "audit_input_digest"
    ):
        reasons.append("auditor_input_digest_mismatch")
    semantic_io_replay = _mapping(verifier.get("semantic_io_replay"))
    if semantic_io_replay and semantic_io_replay.get("status") != "matched":
        reasons.extend(
            str(reason) for reason in semantic_io_replay.get("reasons") or []
        )
    relationship = str(
        transaction.get("auditor_relationship")
        or event.get("auditor_relationship")
        or verifier.get("auditor_relationship")
        or ""
    )
    auditor_model = str(
        transaction.get("audit_model") or verifier.get("audit_model") or ""
    )
    if not auditor_model and relationship in {
        "same_instance",
        "distinct_instance_same_model",
    }:
        auditor_model = str(
            transaction.get("proposal_model") or verifier.get("model") or ""
        )
    return _payload(
        reasons,
        verifier_model=str(
            transaction.get("proposal_model") or verifier.get("model") or ""
        ),
        auditor_model=auditor_model,
        execution_state=_semantic_execution_state(
            event,
            transaction,
            verifier,
            proposal_output=proposal_output,
            audit_output=audit_output,
            typed_pre_audit_stop=typed_pre_audit_stop,
            auditor_relationship=relationship,
        ),
        event_input={
            "question": str(event.get("question") or ""),
            "question_proposition": deepcopy(event.get("question_proposition") or {}),
            "packed_evidence": deepcopy(event.get("packed_evidence") or []),
            "required_slots": deepcopy(event.get("required_slots") or []),
        },
        proposal_input=proposal_input,
        proposal_input_digest=str(transaction.get("proposal_input_digest") or ""),
        proposal_output=proposal_output,
        audit_input=audit_input,
        audit_input_digest=str(transaction.get("audit_input_digest") or ""),
        audit_output=audit_output,
        runtime_outcome=deepcopy(event.get("outcome") or {}),
    )


def _semantic_execution_state(
    event: Mapping[str, Any],
    transaction: Mapping[str, Any],
    verifier: Mapping[str, Any],
    *,
    proposal_output: Mapping[str, Any],
    audit_output: Mapping[str, Any],
    typed_pre_audit_stop: bool,
    auditor_relationship: str,
) -> dict[str, Any]:
    proposal_count = _semantic_call_count(
        verifier.get("proposal_model_call_count"),
        transaction.get("proposal_call_count"),
        proposal_output,
    )
    audit_count = _semantic_call_count(
        verifier.get("audit_model_call_count"),
        transaction.get("audit_call_count"),
        audit_output,
    )
    return {
        "disposition": (
            "typed_pre_audit_stop" if typed_pre_audit_stop else "model_transaction"
        ),
        "stop_reason": (
            str(_mapping(event.get("outcome")).get("reason") or "")
            if typed_pre_audit_stop
            else ""
        ),
        "auditor_relationship": auditor_relationship,
        "proposal_status": (
            "not_started"
            if typed_pre_audit_stop
            else str(
                verifier.get("proposal_status")
                or proposal_output.get("status")
                or "not_started"
            )
        ),
        "audit_status": (
            "not_started"
            if typed_pre_audit_stop
            else str(
                verifier.get("audit_status")
                or audit_output.get("status")
                or "not_started"
            )
        ),
        "proposal_model_call_count": proposal_count,
        "audit_model_call_count": audit_count,
        "actual_model_call_count": proposal_count + audit_count,
    }


def _semantic_call_count(
    verifier_value: Any,
    transaction_value: Any,
    stage: Mapping[str, Any],
) -> int:
    for value in (verifier_value, transaction_value, stage.get("call_count")):
        if isinstance(value, int) and value >= 0:
            return value
    return len(stage.get("attempts") or [])


def _finalizer_scorer_payload(prediction: Mapping[str, Any]) -> dict[str, Any]:
    citation_fields = citation_trace_projection_fields(prediction)
    finalizer = {
        "answer_finalization": deepcopy(prediction.get("answer_finalization") or {}),
        "terminal_semantic_commit": deepcopy(
            prediction.get("terminal_semantic_commit") or {}
        ),
        "engine_terminal_state": deepcopy(
            prediction.get("engine_terminal_state") or {}
        ),
        "engine_verify_decision": deepcopy(
            prediction.get("engine_verify_decision") or {}
        ),
        "terminal_outcome": str(prediction.get("terminal_outcome") or ""),
        "answer_status": str(prediction.get("answer_status") or ""),
        **citation_fields,
    }
    scorer_input = {
        "example_id": str(prediction.get("example_id") or ""),
        "route": str(prediction.get("route") or ""),
        "answer_type": str(prediction.get("answer_type") or ""),
        "modality": str(prediction.get("modality") or ""),
        "predicted_answer": prediction.get("predicted_answer"),
        "answer_for_scoring": prediction.get("answer_for_scoring"),
        "gold_answers": deepcopy(prediction.get("gold_answers") or []),
        "gold_evidence": deepcopy(prediction.get("gold_evidence") or []),
        "predicted_citations": deepcopy(prediction.get("predicted_citations") or []),
        "scored_predicted_sources": deepcopy(
            prediction.get("scored_predicted_sources") or []
        ),
        "expected_formats": deepcopy(prediction.get("expected_formats") or []),
        "expected_guardrails": deepcopy(prediction.get("expected_guardrails") or []),
        "claim_verification": deepcopy(prediction.get("claim_verification") or {}),
        "terminal_outcome": str(prediction.get("terminal_outcome") or ""),
        "terminal_semantic_commit": deepcopy(
            prediction.get("terminal_semantic_commit") or {}
        ),
        "evidence_bundle": deepcopy(prediction.get("evidence_bundle") or {}),
        "example_metadata": deepcopy(prediction.get("example_metadata") or {}),
        "annotation_diagnostics": deepcopy(
            prediction.get("qasper_annotation_diagnostics") or {}
        ),
    }
    scorer_output = {
        "product_metrics": deepcopy(prediction.get("product_metrics") or {}),
        "annotation_scores": deepcopy(prediction.get("qasper_annotation_scores") or []),
        "metrics": deepcopy(prediction.get("metrics") or {}),
        "diagnostics": deepcopy(prediction.get("diagnostics") or {}),
        "verifier_observability": deepcopy(
            prediction.get("verifier_observability") or {}
        ),
        "semantic_answer_evaluation": deepcopy(
            prediction.get("semantic_answer_evaluation") or {}
        ),
        "stage_metrics": deepcopy(prediction.get("stage_metrics") or {}),
        "stage_metric_status": deepcopy(prediction.get("stage_metric_status") or {}),
        "adapter_metrics": deepcopy(prediction.get("adapter_metrics") or {}),
        "external_adapter_metrics": deepcopy(
            prediction.get("external_adapter_metrics") or {}
        ),
    }
    reasons, validation = _finalizer_scorer_reasons(prediction, finalizer)
    if prediction.get("answer_for_scoring") is None:
        reasons.append("scorer_input_answer_missing")
    return _payload(
        reasons,
        terminal_validation=validation,
        finalizer_decision=finalizer,
        finalizer_decision_digest=canonical_digest(finalizer),
        scorer_input=scorer_input,
        scorer_input_digest=canonical_digest(scorer_input),
        scorer_output=scorer_output,
        scorer_output_digest=canonical_digest(scorer_output),
    )


def _finalizer_scorer_reasons(
    prediction: Mapping[str, Any],
    finalizer: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    commit = _mapping(finalizer.get("terminal_semantic_commit"))
    if not commit:
        return ["terminal_semantic_commit_missing"], {
            "terminal_commit_projection_present": False,
            "runtime_projection_present": False,
            "terminal_aliases_consistent": False,
            "scoring_answer_matches_commit": False,
        }
    outcome = terminal_outcome_record(dict(prediction))
    commit_valid = terminal_commit_projection_present(commit)
    runtime_valid = runtime_projection_present(dict(prediction))
    aliases_valid = not outcome["contract_violation"]
    scoring_valid = prediction.get("answer_for_scoring") == commit.get(
        "semantic_answer"
    )
    predicted_valid = prediction.get("predicted_answer") == commit.get(
        "semantic_answer"
    )
    status_valid = finalizer.get("answer_status") == commit.get("answer_status")
    outcome_valid = finalizer.get("terminal_outcome") == commit.get("outcome")
    checks = {
        "terminal_commit_projection_present": commit_valid,
        "runtime_projection_present": runtime_valid,
        "terminal_aliases_consistent": aliases_valid,
        "scoring_answer_matches_commit": scoring_valid,
        "predicted_answer_matches_commit": predicted_valid,
        "answer_status_matches_commit": status_valid,
        "terminal_outcome_matches_commit": outcome_valid,
    }
    reasons = []
    for valid, reason in (
        (commit_valid, "terminal_semantic_commit_projection_invalid"),
        (runtime_valid, "runtime_terminal_projection_invalid"),
        (aliases_valid, "terminal_commit_alias_mismatch"),
        (scoring_valid, "scorer_input_terminal_answer_mismatch"),
        (predicted_valid, "predicted_answer_terminal_commit_mismatch"),
        (status_valid, "answer_status_terminal_commit_mismatch"),
        (outcome_valid, "terminal_outcome_terminal_commit_mismatch"),
    ):
        if not valid:
            reasons.append(reason)
    return reasons, checks


def _provenance_payload(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    run_context: Mapping[str, Any],
) -> dict[str, Any]:
    run = _mapping(run_context.get("run_provenance"))
    git = _mapping(run.get("git"))
    manifest = deepcopy(_mapping(run.get("manifest")))
    config = deepcopy(_mapping(run.get("config")))
    service = deepcopy(_mapping(run.get("service")))
    route = str(prediction.get("route") or "")
    backends = _mapping(run_context.get("backend_metadata"))
    observed_provider_model = _observed_provider_model(
        generator,
        verifier,
        route_backend=_mapping(backends.get(route)),
        service=service,
    )
    (
        provider_model,
        source_prediction_digest,
        replay_reasons,
    ) = _replay_provenance_values(
        prediction,
        observed_provider_model,
        run_context,
    )
    code_identity = {
        "sha": str(git.get("commit") or ""),
        "worktree_path": str(run_context.get("worktree_path") or ""),
        "worktree_clean": git.get("dirty") is False,
    }
    reasons = list(replay_reasons)
    if not _git_sha(code_identity["sha"]):
        reasons.append("code_sha_missing")
    if not code_identity["worktree_path"]:
        reasons.append("worktree_path_missing")
    if code_identity["worktree_clean"] is not True:
        reasons.append("worktree_not_clean")
    if not is_sha256(manifest.get("sha256")):
        reasons.append("manifest_digest_missing")
    if not config:
        reasons.append("run_config_missing")
    if not any(
        provider_model.get(key)
        for key in ("candidate_model", "verifier_model", "auditor_model")
    ):
        reasons.append("provider_model_identity_missing")
    artifact = {
        "source_prediction_digest": source_prediction_digest,
        "artifact_kind": "per_route_prediction_and_semantic_trace",
    }
    return _payload(
        reasons,
        run_provenance={
            "code_identity": code_identity,
            "manifest": manifest,
            "config": config,
            "config_digest": canonical_digest(config),
            "contract_hash": str(run.get("contract_hash") or ""),
            "execution_hash": str(run.get("execution_hash") or ""),
            "provider_model_identity": provider_model,
            "provider_model_identity_digest": canonical_digest(provider_model),
        },
        artifact_binding=artifact,
        artifact_binding_digest=canonical_digest(artifact),
    )


def _observed_provider_model(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    *,
    route_backend: Mapping[str, Any],
    service: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "route_backend": deepcopy(dict(route_backend)),
        "candidate_model": str(generator.get("model") or ""),
        "candidate_tokenizer": str(generator.get("tokenizer_identity") or ""),
        "candidate_tokenizer_endpoint": str(generator.get("tokenizer_endpoint") or ""),
        "verifier_model": str(verifier.get("model") or ""),
        "auditor_model": str(verifier.get("audit_model") or ""),
        "service": deepcopy(dict(service)),
    }


def _replay_provenance_values(
    prediction: Mapping[str, Any],
    observed_provider_model: dict[str, Any],
    run_context: Mapping[str, Any],
) -> tuple[dict[str, Any], str, list[str]]:
    replay = _mapping(run_context.get("causal_replay_provenance"))
    if not replay:
        return observed_provider_model, canonical_digest(prediction), []
    provider_model = deepcopy(_mapping(replay.get("provider_model_identity")))
    source_digest = str(replay.get("source_prediction_digest") or "")
    reasons = []
    if replay.get("contract_id") != "qasper_causal_replay_provenance.v1":
        reasons.append("causal_replay_provenance_contract_invalid")
    if not is_sha256(source_digest):
        reasons.append("causal_replay_source_prediction_digest_missing")
    if canonical_digest(provider_model) != replay.get("provider_model_identity_digest"):
        reasons.append("causal_replay_provider_model_identity_digest_mismatch")
    return provider_model, source_digest, reasons


def _attempt_response_reasons(
    stage: str,
    value: Mapping[str, Any],
    *,
    allow_not_run: bool = False,
) -> list[str]:
    attempts = [
        _mapping(attempt)
        for attempt in value.get("attempts") or []
        if isinstance(attempt, Mapping)
    ]
    if not attempts:
        return [] if allow_not_run else [f"{stage}_attempt_missing"]
    reasons: list[str] = []
    for attempt in attempts:
        if attempt.get("raw_response_truncated") is True:
            reasons.append(f"{stage}_raw_response_truncated")
        if not str(attempt.get("raw_response") or "") and not (
            attempt.get("provider_failure_reason")
            or attempt.get("parse_failure_reason")
        ):
            reasons.append(f"{stage}_raw_response_missing")
    return reasons


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _git_sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(char in "0123456789abcdef" for char in text)
