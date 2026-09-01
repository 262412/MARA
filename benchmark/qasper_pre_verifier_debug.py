from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

_PARSE_FAILURE_REASONS = {
    "json_decode_error",
    "candidate_schema_invalid",
    "candidate_enum_invalid",
}


def pre_verifier_traces(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project a candidate failure even when verification never started."""

    normalized_generator, provider_reason, provider_detail = _normalized_generator(
        generator,
        prediction,
    )
    return normalized_generator, _normalized_verifier(verifier, provider_reason)


def _normalized_generator(
    generator: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> tuple[dict[str, Any], str, str]:
    normalized = deepcopy(dict(generator))
    provider_reason, provider_detail = provider_failure(normalized, prediction)
    normalized.setdefault("contract_id", "qasper_typed_candidate_generation.v2")
    normalized.setdefault("status", "failed" if provider_reason else "not_started")
    normalized.setdefault("failure_reason", provider_reason)
    normalized.setdefault("provider_failure_reason", provider_reason)
    normalized.setdefault("provider_failure_detail", provider_detail)
    for key, default in {
        "message_stack": [],
        "raw_response": "",
        "cleaned_response": "",
        "raw_candidate": "",
        "typed_candidate": "",
        "finish_reason": "",
        "input_digest": "",
        "output_digest": "",
        "transaction_id": "",
        "attempt_id": "",
        "effective_seed": None,
        "attempts": [],
    }.items():
        normalized.setdefault(key, default)
    parse_failure_reason = parse_failure_reason_for(normalized)
    normalized.setdefault("parse_failure_reason", parse_failure_reason)
    normalized.setdefault(
        "execution_failure_kind",
        execution_failure_kind(
            normalized,
            provider_reason=provider_reason,
            parse_failure_reason=parse_failure_reason,
        ),
    )
    normalized["provider_failure"] = {
        "reason": provider_reason,
        "detail": provider_detail,
    }
    for attempt in normalized["attempts"]:
        if not isinstance(attempt, dict):
            continue
        for key, default in {
            "raw_response": "",
            "cleaned_response": "",
            "raw_candidate": "",
            "typed_candidate": "",
            "finish_reason": "",
            "input_digest": normalized.get("input_digest", ""),
            "output_digest": normalized.get("output_digest", ""),
            "provider_failure_reason": provider_reason,
            "provider_failure_detail": provider_detail,
        }.items():
            attempt.setdefault(key, default)
    return normalized, provider_reason, provider_detail


def _normalized_verifier(
    verifier: Mapping[str, Any],
    provider_reason: str,
) -> dict[str, Any]:
    normalized = deepcopy(dict(verifier))
    reason = provider_reason or "candidate_generation_not_completed"
    normalized.setdefault("contract_id", "semantic_proposition_verifier_runtime.v3")
    normalized.setdefault("status", "not_started")
    normalized.setdefault("reason", reason)
    normalized.setdefault("candidate_verification_status", "pre_audit_failed")
    normalized.setdefault("audit_status", "not_started")
    normalized.setdefault("proposal_status", "not_started")
    normalized.setdefault(
        "candidate_verification_audit",
        {
            "contract_id": "candidate_verifier_audit.v2",
            "status": "not_started",
            "mode": "not_started",
            "audited_candidate": "",
            "audited_judgment": "pre_audit_failed",
            "classification": "pre_audit_failed",
            "replacement_candidate_allowed": False,
            "reason": reason,
        },
    )
    return normalized


def pre_verifier_fields(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    provider_reason, provider_detail = provider_failure(generator, prediction)
    parse_failure_reason = parse_failure_reason_for(generator)
    message_stack = deepcopy(generator.get("message_stack") or [])
    finish_reason = generator.get("finish_reason") or ""
    return {
        "provider_failure": {
            "reason": provider_reason,
            "detail": provider_detail,
        },
        "provider_failure_reason": provider_reason,
        "provider_failure_detail": provider_detail,
        "parse_failure_reason": parse_failure_reason,
        "execution_failure_kind": execution_failure_kind(
            generator,
            provider_reason=provider_reason,
            parse_failure_reason=parse_failure_reason,
        ),
        "raw_response": generator.get("raw_response") or "",
        "cleaned_response": generator.get("cleaned_response") or "",
        "raw_candidate": generator.get("raw_candidate") or "",
        "typed_candidate": generator.get("typed_candidate") or "",
        "message_stack": message_stack,
        "final_message_stack": deepcopy(message_stack),
        "finish_reason": finish_reason,
        "effective_seed": generator.get("effective_seed"),
        "input_digest": str(generator.get("input_digest") or ""),
        "output_digest": str(generator.get("output_digest") or ""),
        "transaction_id": str(generator.get("transaction_id") or ""),
        "attempt_id": str(generator.get("attempt_id") or ""),
        "verifier_status": str(verifier.get("status") or "not_started"),
        "auditor_status": str(verifier.get("audit_status") or "not_started"),
        "semantic_verifier_status": str(verifier.get("status") or "not_started"),
        "semantic_auditor_status": str(verifier.get("audit_status") or "not_started"),
    }


def provider_failure(
    generator: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> tuple[str, str]:
    for source in (generator, prediction):
        reason, detail = _explicit_provider_failure(source)
        if reason or detail:
            return reason, detail
    attempts = generator.get("attempts")
    attempts = attempts if isinstance(attempts, list) else []
    for attempt in reversed(attempts):
        if not isinstance(attempt, Mapping):
            continue
        if str(attempt.get("status") or "").strip().casefold() != "provider_failed":
            continue
        return (
            str(
                attempt.get("provider_failure_reason")
                or attempt.get("failure_reason")
                or ""
            ),
            str(
                attempt.get("provider_failure_detail")
                or attempt.get("failure_detail")
                or ""
            ),
        )
    return "", ""


def pre_verifier_terminal_status(
    prediction: Mapping[str, Any],
    terminal_state: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    candidate: str,
) -> tuple[str, bool]:
    terminal_commit = _mapping(prediction.get("terminal_semantic_commit"))
    state_commit = _mapping(terminal_state.get("terminal_semantic_commit"))
    terminal_outcome = (
        str(
            prediction.get("terminal_outcome")
            or terminal_commit.get("outcome")
            or state_commit.get("outcome")
            or terminal_state.get("outcome")
            or ""
        )
        .strip()
        .casefold()
    )
    if terminal_outcome in {"execution_failed", "timeout", "cancelled"}:
        return terminal_outcome, True
    verifier_status = (
        str(
            verifier.get("candidate_verification_status")
            or verifier.get("status")
            or ""
        )
        .strip()
        .casefold()
    )
    audit_status = str(verifier.get("audit_status") or "").strip().casefold()
    generator_status = str(generator.get("status") or "").strip().casefold()
    if verifier_status in {
        "pre_audit_failed",
        "not_started",
        "execution_failed",
        "provider_failed",
        "parse_failed",
        "audit_provider_failed",
        "audit_parse_failed",
    }:
        return terminal_outcome, True
    return terminal_outcome, not candidate and (
        generator_status in {"failed", "provider_failed", "parse_failed", "not_started"}
        or audit_status
        in {
            "not_started",
            "pre_audit_failed",
            "provider_failed",
            "parse_failed",
            "audit_provider_failed",
            "audit_parse_failed",
        }
    )


def candidate_authority_analysis(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    (
        candidate,
        verifier_candidate,
        verifier_status,
        terminal_state,
        terminal_answer,
        answerable,
        candidate_identity_preserved,
        terminal_is_abstention,
    ) = _candidate_context(prediction, generator, verifier)
    (
        terminal_outcome,
        execution_failure_before_verification,
    ) = pre_verifier_terminal_status(
        prediction,
        terminal_state,
        generator,
        verifier,
        candidate,
    )
    false_abstention_cause = _false_abstention_cause(
        generator=generator,
        candidate=candidate,
        candidate_identity_preserved=candidate_identity_preserved,
        verifier_status=verifier_status,
        terminal_is_abstention=terminal_is_abstention,
        answerable=answerable,
        execution_failure_before_verification=execution_failure_before_verification,
    )
    upstream_issue = false_abstention_cause in {
        "upstream_candidate_contract_invalid",
        "upstream_candidate_selected_unanswerable",
        "candidate_contract_identity_mismatch",
    }
    downstream_issue = (
        false_abstention_cause == "downstream_policy_rejected_supported_candidate"
    )
    return {
        "contract_id": "qasper_candidate_authority_analysis.v1",
        "generator_candidate": candidate,
        "verifier_input_candidate": verifier_candidate,
        "verifier_candidate_status": verifier_status,
        "generator_verifier_conflict": bool(
            candidate
            and verifier_candidate == candidate
            and verifier_status == "contradicted"
        ),
        "candidate_identity_preserved": candidate_identity_preserved,
        "upstream_candidate_contract_status": str(generator.get("status") or ""),
        "upstream_candidate_contract_failure_reason": str(
            generator.get("failure_reason") or ""
        ),
        "upstream_candidate_contract_issue": upstream_issue,
        "verifier_rejected_candidate": bool(
            candidate_identity_preserved
            and verifier_status in {"contradicted", "unknown"}
        ),
        "replacement_candidate_allowed": bool(
            verifier.get("replacement_candidate_allowed", False)
        ),
        "semantic_authority_status": str(authority.get("status") or ""),
        "downstream_policy_action": str(
            _mapping(prediction.get("engine_terminal_guardrail_decision")).get("action")
            or _mapping(prediction.get("guardrail_decision")).get("action")
            or ""
        ),
        "terminal_answer": terminal_answer,
        "terminal_outcome": terminal_outcome,
        "execution_failure_before_verification": execution_failure_before_verification,
        "downstream_acceptance_policy_issue": downstream_issue,
        "false_abstention_cause": false_abstention_cause,
    }


def _candidate_context(
    prediction: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> tuple[str, str, str, dict[str, Any], str, bool, bool, bool]:
    candidate = str(generator.get("typed_candidate") or "")
    verifier_candidate = str(verifier.get("candidate_label") or "")
    verifier_status = str(verifier.get("candidate_verification_status") or "")
    terminal_state = _mapping(prediction.get("engine_terminal_state"))
    terminal_answer = str(
        terminal_state.get("semantic_answer")
        or prediction.get("engine_terminal_answer")
        or prediction.get("predicted_answer")
        or ""
    )
    gold = {
        str(value or "").strip().casefold()
        for value in prediction.get("gold_answers") or []
        if str(value or "").strip()
    }
    answerable = bool(gold - {"unanswerable", "insufficient evidence"})
    candidate_identity_preserved = bool(candidate and verifier_candidate == candidate)
    terminal_is_abstention = terminal_answer.strip().casefold() == "unanswerable"
    return (
        candidate,
        verifier_candidate,
        verifier_status,
        terminal_state,
        terminal_answer,
        answerable,
        candidate_identity_preserved,
        terminal_is_abstention,
    )


def _false_abstention_cause(
    *,
    generator: Mapping[str, Any],
    candidate: str,
    candidate_identity_preserved: bool,
    verifier_status: str,
    terminal_is_abstention: bool,
    answerable: bool,
    execution_failure_before_verification: bool = False,
) -> str:
    if (
        execution_failure_before_verification
        or not generator
        or not terminal_is_abstention
        or not answerable
    ):
        return ""
    if str(generator.get("status") or "") != "parsed" or candidate not in {
        "yes",
        "no",
        "unanswerable",
    }:
        return "upstream_candidate_contract_invalid"
    if not candidate_identity_preserved:
        return "candidate_contract_identity_mismatch"
    if candidate == "unanswerable":
        return "upstream_candidate_selected_unanswerable"
    if verifier_status in {"contradicted", "unknown"}:
        return f"verifier_{verifier_status}_candidate"
    if verifier_status == "supported":
        return "downstream_policy_rejected_supported_candidate"
    return "candidate_verifier_status_invalid"


def _explicit_provider_failure(source: Mapping[str, Any]) -> tuple[str, str]:
    failure = source.get("provider_failure")
    failure = failure if isinstance(failure, Mapping) else {}
    reason = str(source.get("provider_failure_reason") or failure.get("reason") or "")
    detail = str(source.get("provider_failure_detail") or failure.get("detail") or "")
    return reason, detail


def parse_failure_reason_for(generator: Mapping[str, Any]) -> str:
    for key in ("parse_failure_reason", "raw_candidate_failure_reason"):
        value = str(generator.get(key) or "").strip()
        if value:
            return value
    failure_reason = str(generator.get("failure_reason") or "").strip()
    if failure_reason.casefold() in _PARSE_FAILURE_REASONS:
        return failure_reason
    attempts = generator.get("attempts")
    attempts = attempts if isinstance(attempts, list) else []
    for attempt in reversed(attempts):
        if not isinstance(attempt, Mapping):
            continue
        for key in ("parse_failure_reason", "raw_candidate_failure_reason"):
            value = str(attempt.get(key) or "").strip()
            if value:
                return value
        value = str(attempt.get("failure_reason") or "").strip()
        if (
            str(attempt.get("status") or "").strip().casefold() != "provider_failed"
            and value.casefold() in _PARSE_FAILURE_REASONS
        ):
            return value
    return ""


def execution_failure_kind(
    generator: Mapping[str, Any],
    *,
    provider_reason: str,
    parse_failure_reason: str,
) -> str:
    if provider_reason:
        return "provider_failure"
    if parse_failure_reason:
        return "candidate_parse_failure"
    if str(generator.get("status") or "").strip().casefold() in {
        "failed",
        "provider_failed",
        "parse_failed",
        "pre_audit_failed",
    }:
        return "candidate_generation_failure"
    return ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
