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
    source_packing = _mapping(lineage.get("source_packing"))
    selector = _mapping(lineage.get("selector"))
    plan_construction = _mapping(lineage.get("plan_construction"))
    transaction = _semantic_model_transaction(verifier)
    debug_proposal = _mapping(transaction.get("proposal"))
    debug_audit = _mapping(transaction.get("audit"))
    parsed_proposal = _mapping(
        _last_attempt(debug_proposal.get("attempts")).get("parsed_value")
    )
    selected_plan_id = str(projection.get("selected_plan_id") or "")
    expected_status = (
        "failed"
        if _lineage_failure_expected(
            verifier,
            plan_construction,
        )
        else "passed"
    )
    return bool(
        lineage.get("contract_id") == "semantic_proposition_data_lineage.v1"
        and status == expected_status
        and _lineage_identities_match(identities, verifier)
        and _source_packing_complete(source_packing, identities)
        and _selector_lineage_complete(selector)
        and _plan_construction_complete(plan_construction, selector)
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


def _lineage_failure_expected(
    verifier: dict[str, Any],
    plan_construction: dict[str, Any],
) -> bool:
    audit_failed = (
        _mapping(verifier.get("candidate_verification_audit")).get("status") == "failed"
    )
    return bool(audit_failed or plan_construction.get("status") == "failed")


def _source_packing_complete(
    value: dict[str, Any],
    identities: dict[str, Any],
) -> bool:
    source_records = _list(value.get("source_records"))
    packed_records = _list(value.get("records"))
    return bool(
        value.get("status") == "passed"
        and value.get("contract_id") == "qasper_source_packing_observation.v1"
        and value.get("semantic_pack_digest") == identities.get("semantic_pack_digest")
        and _sha256_digest(value.get("source_semantic_pack_digest"))
        and source_records
        and packed_records
        and all(_source_record_complete(record) for record in source_records)
        and all(_packed_record_complete(record) for record in packed_records)
    )


def _source_record_complete(value: Any) -> bool:
    record = _mapping(value)
    return bool(
        record.get("evidence_id")
        and _sha256_digest(record.get("text_digest"))
        and int(record.get("semantic_rank") or 0) > 0
        and isinstance(record.get("selected_for_windowing"), bool)
        and isinstance(record.get("packed"), bool)
        and record.get("stop_stage")
        in {"bounded_source_selection", "fit_to_input_budget", "packed"}
    )


def _packed_record_complete(value: Any) -> bool:
    record = _mapping(value)
    return bool(
        record.get("evidence_id")
        and _sha256_digest(record.get("text_digest"))
        and _list(record.get("selector_refs"))
    )


def _selector_lineage_complete(value: dict[str, Any]) -> bool:
    refs = _list(value.get("universe_refs"))
    records = _list(value.get("universe_records"))
    record_refs = {str(_mapping(record).get("selector_id") or "") for record in records}
    return bool(
        value.get("status") == "passed"
        and refs
        and records
        and set(str(ref) for ref in refs) == record_refs
        and int(value.get("candidate_count") or 0) > 0
        and _list(value.get("event_ids"))
    )


def _plan_construction_complete(
    value: dict[str, Any],
    selector: dict[str, Any],
) -> bool:
    universe = [str(ref) for ref in _list(value.get("universe_refs"))]
    selector_universe = [str(ref) for ref in _list(selector.get("universe_refs"))]
    semantic_status = str(value.get("semantic_plan_status") or "")
    transport_status = str(value.get("transport_status") or "")
    return bool(
        value.get("status") in {"passed", "failed"}
        and semantic_status in {"passed", "failed", "not_applicable"}
        and transport_status in {"passed", "failed", "not_run", "not_applicable"}
        and universe == selector_universe
        and int(value.get("candidate_count") or 0) >= 0
        and int(value.get("legal_plan_count") or 0) >= 0
        and isinstance(value.get("required_slots"), list)
        and isinstance(value.get("covered_slots"), list)
        and isinstance(value.get("required_object_tokens"), list)
        and isinstance(value.get("covered_object_tokens"), list)
        and (semantic_status != "failed" or bool(value.get("reason")))
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
