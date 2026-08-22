from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable, Mapping

QASPER_SEMANTIC_DEBUG_CONTRACT = "qasper_semantic_pipeline_debug.v2"
SEMANTIC_PROPOSITION_DEBUG_CONTRACT = "semantic_proposition_debug_trace.v2"

_RECOVERY_STAGES = {
    "evidence_rebind",
    "focused_retrieval",
    "reverify",
    "targeted_retrieval",
    "typed_boolean_generation_recovery",
}


def qasper_semantic_debug_rows(
    predictions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        metadata = _terminal_metadata(prediction)
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        debug_trace = _mapping(verifier.get("debug_trace"))
        if debug_trace.get("contract_id") != SEMANTIC_PROPOSITION_DEBUG_CONTRACT:
            continue
        authority = _mapping(metadata.get("semantic_proposition_authority"))
        query_plan = _mapping(
            metadata.get("query_plan") or metadata.get("bound_query_plan")
        )
        recovery_events = _recovery_events(prediction)
        row = {
            "contract_id": QASPER_SEMANTIC_DEBUG_CONTRACT,
            "example_id": prediction.get("example_id"),
            "route": prediction.get("route"),
            "question": prediction.get("question"),
            "gold_answers": deepcopy(prediction.get("gold_answers") or []),
            "predicted_answer": prediction.get("predicted_answer"),
            "answer_status": prediction.get("answer_status"),
            "failure_taxonomy": prediction.get("failure_taxonomy"),
            "terminal_outcome": prediction.get("terminal_outcome"),
            "terminal_outcome_reason": prediction.get("terminal_outcome_reason"),
            "semantic_verifier": deepcopy(verifier),
            "semantic_authority": deepcopy(authority),
            "recovery_events": recovery_events,
            "required_slot_states": _required_slot_states(query_plan),
            "final_typed_authority": _final_typed_authority(prediction),
        }
        row["findings"] = _findings(row)
        rows.append(row)
    return rows


def qasper_semantic_debug_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    counts = Counter(
        str(finding.get("code") or "")
        for row in rows
        for finding in row.get("findings", [])
        if finding.get("code")
    )
    return {
        "qasper_semantic_debug_trace_count": len(rows),
        "qasper_semantic_debug_finding_count": sum(counts.values()),
        "qasper_semantic_debug_findings": dict(sorted(counts.items())),
    }


def _terminal_metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    bundle = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    metadata = _mapping(bundle.get("metadata"))
    return metadata or _mapping(prediction.get("evidence_metadata"))


def _recovery_events(prediction: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(event)
        for event in prediction.get("controller_trace", []) or []
        if isinstance(event, dict) and event.get("stage") in _RECOVERY_STAGES
    ]


def _required_slot_states(query_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for slot in query_plan.get("evidence_slots", []) or []:
        if not isinstance(slot, Mapping) or not slot.get("required_for_verification"):
            continue
        states.append(
            {
                "slot_id": slot.get("slot_id"),
                "status": slot.get("status"),
                "evidence_ids": deepcopy(slot.get("evidence_ids") or []),
            }
        )
    return states


def _final_typed_authority(prediction: Mapping[str, Any]) -> dict[str, Any]:
    terminal_state = _mapping(prediction.get("engine_terminal_state"))
    authority = _mapping(terminal_state.get("typed_authority"))
    if authority:
        return deepcopy(authority)
    verify = _mapping(prediction.get("engine_verify_decision"))
    return deepcopy(_mapping(verify.get("typed_authority")))


def _findings(row: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    verifier = _mapping(row.get("semantic_verifier"))
    authority = _mapping(row.get("semantic_authority"))
    debug_trace = _mapping(verifier.get("debug_trace"))
    events = [
        event for event in debug_trace.get("events", []) if isinstance(event, Mapping)
    ]
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
    findings.extend(_recovery_state_findings(row))
    if int(debug_trace.get("dropped_event_count") or 0) > 0:
        findings.append(
            _finding(
                "semantic_debug_history_truncated",
                "trace_integrity",
                "semantic debug history exceeded its bounded event limit",
            )
        )
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
        audit.get("contract_id") != "conclusion_audit.v1"
        or any(
            audit.get(field) is not True
            for field in (
                "conclusion_entailed",
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
