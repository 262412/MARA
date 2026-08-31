from __future__ import annotations

from typing import Any, Mapping


def findings_for_row(row: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    verifier = _mapping(row.get("semantic_verifier"))
    authority = _mapping(row.get("semantic_authority"))
    debug_trace = _mapping(verifier.get("debug_trace"))
    events = [
        event for event in debug_trace.get("events", []) if isinstance(event, Mapping)
    ]
    candidate_analysis = _mapping(row.get("candidate_authority_analysis"))
    findings.extend(_canonical_digest_findings(row))
    findings.extend(_candidate_findings(candidate_analysis))
    if (
        verifier.get("audit_status") == "verified"
        and authority.get("status") == "rejected"
    ):
        findings.append(
            _finding(
                "audit_verified_authority_rejected",
                "inconsistency",
                str(authority.get("reason") or "authority_rejected"),
            )
        )
    if any(_same_instance_audit_executed(event) for event in events):
        findings.append(
            _finding(
                "same_instance_proposal_and_audit",
                "independence_risk",
                "proposal and entailment audit used the same model instance",
            )
        )
    findings.extend(_audit_contract_findings(verifier))
    findings.extend(_consistency_findings(row))
    findings.extend(_recovery_state_findings(row))
    findings.extend(_trace_integrity_findings(debug_trace))
    findings.extend(_benchmark_findings(row, events, authority))
    return findings


def _canonical_digest_findings(row: Mapping[str, Any]) -> list[dict[str, str]]:
    trace = _mapping(row.get("canonical_projection_digest_trace"))
    if trace.get("status") != "mismatch":
        return []
    boundary = str(
        _mapping(trace.get("first_divergence")).get("boundary")
        or trace.get("boundary")
        or "canonical_projection_digest"
    )
    return [
        _finding(
            "canonical_projection_digest_mismatch",
            "inconsistency",
            f"first semantic digest divergence at {boundary}",
        )
    ]


def _candidate_findings(
    candidate_analysis: Mapping[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if candidate_analysis.get("generator_verifier_conflict"):
        findings.append(
            _finding(
                "generator_verifier_candidate_conflict",
                "candidate_verification",
                str(
                    candidate_analysis.get("verifier_candidate_status")
                    or "contradicted"
                ),
            )
        )
    if candidate_analysis.get("false_abstention_cause"):
        findings.append(
            _finding(
                "false_abstention_causal_boundary",
                "answer_acceptance",
                str(candidate_analysis.get("false_abstention_cause") or ""),
            )
        )
    return findings


def _consistency_findings(row: Mapping[str, Any]) -> list[dict[str, str]]:
    if not row.get("auditor_internal_inconsistency"):
        return []
    return [
        _finding(
            "auditor_internal_inconsistency",
            "inconsistency",
            "auditor rejected a fragment that is an exact normalized substring of its bound quote",
        )
    ]


def _trace_integrity_findings(
    debug_trace: Mapping[str, Any],
) -> list[dict[str, str]]:
    if int(debug_trace.get("dropped_event_count") or 0) <= 0:
        return []
    return [
        _finding(
            "semantic_debug_history_truncated",
            "trace_integrity",
            "semantic debug history exceeded its bounded event limit",
        )
    ]


def _benchmark_findings(
    row: Mapping[str, Any],
    events: list[Mapping[str, Any]],
    authority: Mapping[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if _positive_verdict_against_negative_gold(row, events):
        findings.append(
            _finding(
                "positive_verdict_against_negative_gold",
                "benchmark_diagnostic",
                "a positive semantic verdict was accepted for a negative benchmark answer",
            )
        )
    if authority.get("status") == "verified" and not _required_slots_verified(row):
        findings.append(
            _finding(
                "verified_authority_required_slot_mismatch",
                "inconsistency",
                "authority was verified while a required QueryPlan slot remained unverified",
            )
        )
    return findings


def _audit_contract_findings(verifier: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = []
    if _verified_conclusion_audit_missing(verifier):
        findings.append(
            _finding(
                "verified_audit_conclusion_contract_missing",
                "inconsistency",
                "a verified semantic audit has no complete typed conclusion audit",
            )
        )
    if _proof_repair_without_full_reaudit(verifier):
        findings.append(
            _finding(
                "proof_repair_without_full_reaudit",
                "inconsistency",
                "proof repair was recorded without a complete independent reaudit",
            )
        )
    return findings


def _recovery_state_findings(row: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = []
    if any(
        _reverify_without_pack_change(event) for event in row.get("recovery_events", [])
    ):
        findings.append(
            _finding(
                "reverify_without_semantic_pack_change",
                "recovery_state",
                "semantic reverification ran although the semantic pack was unchanged",
            )
        )
    if any(
        event.get("stop_reason") == "recovery_no_progress"
        for event in row.get("recovery_events", [])
    ):
        findings.append(
            _finding(
                "recovery_stopped_without_state_change",
                "recovery_state",
                "recovery terminated because evidence, slots, and authority did not change",
            )
        )
    return findings


def _verified_conclusion_audit_missing(verifier: Mapping[str, Any]) -> bool:
    if not str(verifier.get("audit_status") or "").startswith("verified"):
        return False
    audit = _mapping(verifier.get("conclusion_audit"))
    return bool(
        audit.get("contract_id") != "conclusion_audit.v2"
        or any(
            audit.get(field) is not True
            for field in (
                "conclusion_entailed",
                "actor_consistent",
                "predicate_consistent",
                "object_consistent",
                "polarity_consistent",
                "quantifier_consistent",
                "scope_consistent",
            )
        )
    )


def _proof_repair_without_full_reaudit(verifier: Mapping[str, Any]) -> bool:
    transitions = verifier.get("recovery_transitions") or []
    repaired = any(
        isinstance(value, Mapping) and value.get("to") == "proof_repair"
        for value in transitions
    )
    return bool(repaired and verifier.get("full_reaudit") is not True)


def _reverify_without_pack_change(event: Any) -> bool:
    return bool(
        isinstance(event, Mapping)
        and event.get("stage") == "reverify"
        and event.get("semantic_pack_digest_applicable") is True
        and event.get("semantic_pack_digest_changed") is not True
    )


def _same_instance_audit_executed(event: Mapping[str, Any]) -> bool:
    outcome = _mapping(event.get("outcome"))
    return event.get("auditor_relationship") == "same_instance" and outcome.get(
        "audit_status"
    ) not in {None, "", "not_started", "not_required"}


def _positive_verdict_against_negative_gold(
    row: Mapping[str, Any], events: list[Mapping[str, Any]]
) -> bool:
    gold = {str(value).strip().casefold() for value in row.get("gold_answers", [])}
    if "no" not in gold:
        return False
    return any(_accepted_positive_verdict(event) for event in events)


def _accepted_positive_verdict(event: Mapping[str, Any]) -> bool:
    outcome = _mapping(event.get("outcome"))
    return (
        outcome.get("verdict") == "yes"
        and outcome.get("status") == "parsed"
        and outcome.get("audit_status") == "verified"
    )


def _required_slots_verified(row: Mapping[str, Any]) -> bool:
    states = row.get("required_slot_states", []) or []
    return bool(states) and all(
        isinstance(slot, Mapping) and slot.get("status") == "verified_support"
        for slot in states
    )


def _finding(code: str, category: str, detail: str) -> dict[str, str]:
    return {"code": code, "category": category, "detail": detail}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
