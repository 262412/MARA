from __future__ import annotations

import hashlib
from typing import Any

from scripts.slurm.qasper_debug_contract_support import _mapping


def semantic_data_lineage_complete(verifier: dict[str, Any]) -> bool:
    lineage = _mapping(verifier.get("semantic_data_lineage"))
    identities = _mapping(lineage.get("identities"))
    proposal_contract = _mapping(lineage.get("proposal_contract"))
    projection = _mapping(lineage.get("local_projection"))
    proposal_attempts = _list(lineage.get("proposal_attempts"))
    audit = _mapping(lineage.get("audit"))
    audit_attempts = _list(audit.get("attempts"))
    status = str(lineage.get("status") or "")
    first_inconsistency = _mapping(lineage.get("first_inconsistency"))
    transaction = _semantic_model_transaction(verifier)
    debug_proposal = _mapping(transaction.get("proposal"))
    debug_audit = _mapping(transaction.get("audit"))
    parsed_proposal = _mapping(
        _last_attempt(debug_proposal.get("attempts")).get("parsed_value")
    )
    selected_plan_id = str(projection.get("selected_plan_id") or "")
    expected_status = (
        "failed"
        if _mapping(verifier.get("candidate_verification_audit")).get("status")
        == "failed"
        else "passed"
    )
    return bool(
        lineage.get("contract_id") == "semantic_proposition_data_lineage.v1"
        and status == expected_status
        and _lineage_identities_match(identities, verifier)
        and proposal_contract.get("mode") == "canonical_plan_selection"
        and _sha256_digest(proposal_contract.get("response_schema_digest"))
        and proposal_attempts
        and all(_lineage_attempt_complete(attempt) for attempt in proposal_attempts)
        and _lineage_attempts_match(
            proposal_attempts,
            debug_proposal.get("attempts"),
        )
        and projection.get("status") == "passed"
        and selected_plan_id
        == str(parsed_proposal.get("canonical_evidence_plan_id") or "")
        and (
            not selected_plan_id
            or selected_plan_id in set(proposal_contract.get("allowed_plan_ids") or [])
        )
        and audit.get("status") == "parsed"
        and audit_attempts
        and all(_lineage_attempt_complete(attempt) for attempt in audit_attempts)
        and _lineage_attempts_match(audit_attempts, debug_audit.get("attempts"))
        and (
            (
                not first_inconsistency
                or _lineage_inconsistency_complete(first_inconsistency)
            )
            if status == "passed"
            else _lineage_inconsistency_complete(first_inconsistency)
        )
    )


def _lineage_identities_match(
    identities: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    fields = (
        "semantic_pack_digest",
        "canonical_span_universe_digest",
        "candidate_transaction_id",
    )
    return bool(
        all(str(identities.get(field) or "") for field in fields)
        and all(identities.get(field) == verifier.get(field) for field in fields)
    )


def _lineage_attempt_complete(value: Any) -> bool:
    attempt = _mapping(value)
    return bool(
        int(attempt.get("attempt") or 0) > 0
        and (
            _sha256_digest(attempt.get("raw_response_digest"))
            or bool(attempt.get("provider_failure_reason"))
        )
        and "parse_failure_reason" in attempt
        and "provider_failure_reason" in attempt
    )


def _lineage_inconsistency_complete(value: dict[str, Any]) -> bool:
    stage = str(value.get("stage") or "")
    return bool(
        stage
        and value.get("reason")
        and int(value.get("attempt") or 0) > 0
        and (
            _sha256_digest(value.get("raw_response_digest"))
            or stage in {"proposal_provider", "audit_provider"}
        )
    )


def _lineage_attempts_match(
    lineage_attempts: list[Any],
    raw_debug_attempts: Any,
) -> bool:
    debug_attempts = _list(raw_debug_attempts)
    if len(lineage_attempts) != len(debug_attempts):
        return False
    for lineage_value, debug_value in zip(lineage_attempts, debug_attempts):
        lineage_attempt = _mapping(lineage_value)
        debug_attempt = _mapping(debug_value)
        if not _lineage_attempt_matches(lineage_attempt, debug_attempt):
            return False
    return True


def _lineage_attempt_matches(
    lineage_attempt: dict[str, Any],
    debug_attempt: dict[str, Any],
) -> bool:
    raw_response = debug_attempt.get("raw_response")
    raw_response = raw_response if isinstance(raw_response, str) else ""
    expected_digest = (
        hashlib.sha256(raw_response.encode("utf-8")).hexdigest() if raw_response else ""
    )
    return bool(
        lineage_attempt.get("attempt") == debug_attempt.get("attempt")
        and str(lineage_attempt.get("raw_response_digest") or "") == expected_digest
        and str(lineage_attempt.get("parse_failure_reason") or "")
        == str(debug_attempt.get("parse_failure_reason") or "")
        and str(lineage_attempt.get("provider_failure_reason") or "")
        == str(debug_attempt.get("provider_failure_reason") or "")
    )


def _semantic_model_transaction(verifier: dict[str, Any]) -> dict[str, Any]:
    debug = _mapping(verifier.get("debug_trace"))
    events = [event for event in debug.get("events") or [] if isinstance(event, dict)]
    source_index = verifier.get("cache_source_event_index")
    if verifier.get("cache_hit") is True and isinstance(source_index, int):
        selected = next(
            (
                event
                for event in events
                if event.get("event_index") == source_index
                and event.get("event") == "model_transaction"
            ),
            None,
        )
        return _mapping((selected or {}).get("transaction"))
    transactions = [
        event for event in events if event.get("event") == "model_transaction"
    ]
    return _mapping(transactions[-1].get("transaction")) if transactions else {}


def _last_attempt(value: Any) -> dict[str, Any]:
    attempts = _list(value)
    return _mapping(attempts[-1]) if attempts else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _sha256_digest(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )
