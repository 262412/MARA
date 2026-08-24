from __future__ import annotations

from typing import Any

from scripts.slurm.qasper_debug_contract_support import (
    _CANDIDATE_VERIFIER_AUDIT_CONTRACT,
    _CONCLUSION_AUDIT_CONTRACT,
    _SEMANTIC_DEBUG_TRACE_CONTRACT,
    _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
    _SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
    _mapping,
    _require,
)


def _schema_version_violations(
    verifier: dict[str, Any],
    prefix: str,
) -> list[str]:
    violations: list[str] = []
    debug = _mapping(verifier.get("debug_trace"))
    _require(
        violations,
        debug.get("contract_id") == _SEMANTIC_DEBUG_TRACE_CONTRACT,
        f"semantic_debug_schema_version_invalid:{prefix}",
    )
    for field in ("proposal_contract", "semantic_proposition_verdict_contract"):
        value = verifier.get(field)
        if value is not None and value != "":
            _require(
                violations,
                value == _SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                f"semantic_proposition_verdict_schema_version_invalid:{prefix}",
            )
    direct_conclusion_audit = _mapping(verifier.get("conclusion_audit"))
    if direct_conclusion_audit:
        _require(
            violations,
            direct_conclusion_audit.get("contract_id") == _CONCLUSION_AUDIT_CONTRACT,
            f"conclusion_audit_schema_version_invalid:{prefix}",
        )
    candidate_audit = _mapping(verifier.get("candidate_verification_audit"))
    audit_contract = (
        _CANDIDATE_VERIFIER_AUDIT_CONTRACT
        if verifier.get("candidate_verification_status") == "unknown"
        or candidate_audit.get("mode") == "candidate_bound_unknown_audit"
        else _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT
    )
    for field in ("audit_contract_id", "semantic_entailment_audit_contract"):
        value = verifier.get(field)
        if value is not None and value != "":
            expected = (
                audit_contract
                if field == "audit_contract_id"
                else _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT
            )
            _require(
                violations,
                value == expected,
                f"semantic_entailment_audit_schema_version_invalid:{prefix}",
            )
    for field in ("entailment_audit", "semantic_entailment_audit"):
        audit = _mapping(verifier.get(field))
        if audit:
            _require(
                violations,
                audit.get("contract_id") == _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
                f"semantic_entailment_audit_schema_version_invalid:{prefix}",
            )
            conclusion_audit = _mapping(audit.get("conclusion_audit"))
            if conclusion_audit:
                _require(
                    violations,
                    conclusion_audit.get("contract_id") == _CONCLUSION_AUDIT_CONTRACT,
                    f"conclusion_audit_schema_version_invalid:{prefix}",
                )
    violations.extend(_schema_debug_event_violations(debug, prefix))
    return violations


def _schema_debug_event_violations(
    debug: dict[str, Any],
    prefix: str,
) -> list[str]:
    violations: list[str] = []
    for event in debug.get("events") or []:
        if not isinstance(event, dict) or event.get("event") != "model_transaction":
            continue
        outcome = _mapping(event.get("outcome"))
        typed_conclusion = _mapping(outcome.get("typed_conclusion"))
        if typed_conclusion:
            _require(
                violations,
                typed_conclusion.get("contract_id") == "typed_conclusion.v1",
                f"typed_conclusion_schema_version_invalid:{prefix}",
            )
        conclusion_audit = _mapping(outcome.get("conclusion_audit"))
        if conclusion_audit:
            _require(
                violations,
                conclusion_audit.get("contract_id") == _CONCLUSION_AUDIT_CONTRACT,
                f"conclusion_audit_schema_version_invalid:{prefix}",
            )
        transaction = _mapping(event.get("transaction"))
        proposal = _mapping(transaction.get("proposal"))
        violations.extend(_schema_proposal_attempt_violations(proposal, prefix))
        audit = _mapping(transaction.get("audit"))
        violations.extend(_schema_audit_attempt_violations(audit, prefix))
    return violations


def _schema_proposal_attempt_violations(
    proposal: dict[str, Any],
    prefix: str,
) -> list[str]:
    violations: list[str] = []
    for attempt in proposal.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        parsed_value = _mapping(attempt.get("parsed_value"))
        if parsed_value:
            _require(
                violations,
                parsed_value.get("contract_id")
                == _SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                f"semantic_proposition_verdict_schema_version_invalid:{prefix}",
            )
    return violations


def _schema_audit_attempt_violations(
    audit: dict[str, Any],
    prefix: str,
) -> list[str]:
    violations: list[str] = []
    for attempt in audit.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        parsed_value = _mapping(attempt.get("parsed_value"))
        contract_id = parsed_value.get("contract_id")
        if contract_id is None or contract_id == "":
            continue
        _require(
            violations,
            contract_id == _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
            f"semantic_entailment_audit_schema_version_invalid:{prefix}",
        )
        conclusion_audit = _mapping(parsed_value.get("conclusion_audit"))
        if conclusion_audit:
            _require(
                violations,
                conclusion_audit.get("contract_id") == _CONCLUSION_AUDIT_CONTRACT,
                f"conclusion_audit_schema_version_invalid:{prefix}",
            )
    return violations


def _relation_flags_valid(verifier: dict[str, Any], relation: str) -> bool:
    verdict = str(verifier.get("verdict") or "").strip().casefold()
    return bool(
        verdict in {"yes", "no", "insufficient_evidence"}
        and verifier.get("explicit_contradiction") is (verdict == "no")
        and verifier.get("candidate_verifier_disagreement")
        is (relation == "contradicted")
        and verifier.get("unknown") is (relation == "unknown")
    )


def _audit_relation_consistent(
    verifier: dict[str, Any],
    relation: str,
) -> bool:
    """Keep audit classification/verdict aligned without deriving flags from it."""

    audit = _mapping(verifier.get("candidate_verification_audit"))
    audited_relation = str(audit.get("audited_judgment") or "").strip().casefold()
    if audited_relation != relation:
        return False
    candidate = str(verifier.get("candidate_label") or "").strip().casefold()
    verdict = str(audit.get("audited_verdict") or "").strip().casefold()
    classification = str(audit.get("classification") or "").strip().casefold()
    expected = _expected_audit_outcome(candidate, relation)
    return expected is not None and (verdict, classification) in expected


def _expected_audit_outcome(
    candidate: str,
    relation: str,
) -> set[tuple[str, str]] | None:
    if candidate not in {"yes", "no", "unanswerable"}:
        return None
    if relation == "unknown":
        return {("insufficient_evidence", "unknown")}
    if relation == "supported":
        if candidate == "unanswerable":
            return {("insufficient_evidence", "unknown")}
        return {(candidate, "supported")}
    if relation == "contradicted":
        verdicts = {"yes", "no"} - (
            {candidate} if candidate != "unanswerable" else set()
        )
        return {(verdict, "explicit_contradiction") for verdict in verdicts}
    return None


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
