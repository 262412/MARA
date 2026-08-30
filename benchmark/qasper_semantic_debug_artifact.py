from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable, Mapping

from .qasper_candidate_input_state import candidate_input_state_observation
from .qasper_causal_evidence_chain import qasper_causal_evidence_chain
from .qasper_causal_transaction import qasper_causal_transaction
from .qasper_pre_verifier_debug import (
    candidate_authority_analysis as _candidate_authority_analysis,
)
from .qasper_pre_verifier_debug import pre_verifier_fields as _pre_verifier_fields
from .qasper_pre_verifier_debug import pre_verifier_traces as _pre_verifier_traces
from .qasper_semantic_debug_findings import findings_for_row

QASPER_SEMANTIC_DEBUG_CONTRACT = "qasper_semantic_pipeline_debug.v3"
SEMANTIC_PROPOSITION_DEBUG_CONTRACT = "semantic_proposition_debug_trace.v3"

_RECOVERY_STAGES = {
    "evidence_rebind",
    "focused_retrieval",
    "reverify",
    "targeted_retrieval",
    "typed_boolean_generation_recovery",
}


def qasper_semantic_debug_rows(
    predictions: Iterable[dict[str, Any]],
    *,
    include_missing: bool = False,
    run_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        row = _debug_row(
            prediction,
            include_missing=include_missing,
            run_context=run_context,
        )
        if row is not None:
            rows.append(row)
    return rows


def _debug_row(
    prediction: dict[str, Any],
    *,
    include_missing: bool,
    run_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    metadata = _terminal_metadata(prediction)
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    debug_trace = _mapping(verifier.get("debug_trace"))
    generator = _mapping(metadata.get("qasper_candidate_generation"))
    has_debug_trace = (
        debug_trace.get("contract_id") == SEMANTIC_PROPOSITION_DEBUG_CONTRACT
    )
    if not has_debug_trace and not generator and not include_missing:
        return None
    if not has_debug_trace:
        generator, verifier = _pre_verifier_traces(
            prediction,
            generator,
            verifier,
        )
    authority = _mapping(metadata.get("semantic_proposition_authority"))
    query_plan = _mapping(
        metadata.get("query_plan") or metadata.get("bound_query_plan")
    )
    transaction_event = _latest_transaction_event(debug_trace)
    rejected_transactions = _rejected_transactions(verifier, authority)
    row = _base_row(
        prediction,
        verifier,
        authority,
        query_plan,
        _recovery_events(prediction),
        transaction_event,
        rejected_transactions,
    )
    row.update(_v3_fields(prediction, generator, verifier, authority))
    row.update(_pre_verifier_fields(prediction, generator, verifier))
    row["causal_transaction"] = qasper_causal_transaction(
        prediction,
        row,
        run_context=run_context,
        origin="online",
    )
    row["causal_evidence_chain"] = qasper_causal_evidence_chain(row)
    row["findings"] = findings_for_row(row)
    return row


def _base_row(
    prediction: dict[str, Any],
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
    query_plan: Mapping[str, Any],
    recovery_events: list[dict[str, Any]],
    transaction_event: Mapping[str, Any],
    rejected_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
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
        "terminal_semantic_commit": deepcopy(
            prediction.get("terminal_semantic_commit") or {}
        ),
        "semantic_verifier": deepcopy(verifier),
        "semantic_authority": deepcopy(authority),
        "question_proposition_resolution": deepcopy(
            verifier.get("question_proposition_resolution") or {}
        ),
        "proof_mode": str(verifier.get("proof_mode") or ""),
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "cache_source": str(verifier.get("cache_source") or ""),
        "recovery_transitions": deepcopy(verifier.get("recovery_transitions") or []),
        "rejected_transactions": rejected_transactions,
        "auditor_internal_inconsistency": bool(
            verifier.get("auditor_internal_inconsistency")
        ),
        "auditor_internal_inconsistency_count": int(
            verifier.get("auditor_internal_inconsistency_count") or 0
        ),
        "local_premise_consistency": deepcopy(
            verifier.get("local_premise_consistency") or {}
        ),
        "local_premise_consistency_history": deepcopy(
            verifier.get("local_premise_consistency_history") or []
        ),
        "recovery_events": recovery_events,
        "required_slot_states": _required_slot_states(query_plan),
        "final_typed_authority": _final_typed_authority(prediction),
        "audited_typed_conclusion": _audited_typed_conclusion(
            verifier, transaction_event, rejected_transactions
        ),
        "audited_conclusion_audit": _audited_conclusion_audit(
            verifier, transaction_event, rejected_transactions
        ),
        "polarity_contradiction_check": _audited_polarity_check(
            verifier, authority, rejected_transactions
        ),
        "raw_audit_call_rejected": _raw_audit_call_rejected(
            verifier, transaction_event
        ),
        "final_row_audit_rejected": _final_row_audit_rejected(
            verifier, transaction_event
        ),
        "audit_verified_but_runtime_rejected": _audit_verified_but_runtime_rejected(
            verifier, authority, transaction_event
        ),
    }


def _v3_fields(
    prediction: dict[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "main_candidate_generator": deepcopy(generator),
        "candidate_transformation_stages": deepcopy(
            generator.get("transformation_stages") or []
        ),
        "claim_aggregation_events": _claim_aggregation_events(prediction),
        "qasper_annotation_scores": deepcopy(
            prediction.get("qasper_annotation_scores") or []
        ),
        "qasper_annotation_diagnostics": deepcopy(
            prediction.get("qasper_annotation_diagnostics") or {}
        ),
        "transaction_identity": _transaction_identity(generator, verifier),
        "candidate_input_state_observation": candidate_input_state_observation(
            _terminal_metadata(prediction)
        ),
    }
    fields["candidate_authority_analysis"] = _candidate_authority_analysis(
        prediction, generator, verifier, authority
    )
    fields["structural_coverage"] = _structural_coverage(
        {**fields, "semantic_verifier": verifier}
    )
    fields["online_model_coverage"] = _online_model_coverage(generator, verifier)
    return fields


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


def _claim_aggregation_events(
    prediction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        deepcopy(event)
        for event in prediction.get("controller_trace", []) or []
        if isinstance(event, dict) and event.get("stage") == "claim_aggregation"
    ]


def _transaction_identity(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_cross_route_transaction_trace.v1",
        "trace_group_id": str(
            generator.get("trace_group_id") or verifier.get("trace_group_id") or ""
        ),
        "generator_transaction_id": str(generator.get("transaction_id") or ""),
        "generator_attempt_id": str(generator.get("attempt_id") or ""),
        "verifier_transaction_id": str(verifier.get("transaction_id") or ""),
        "verifier_attempt_id": str(verifier.get("attempt_id") or ""),
        "auditor_attempt_id": str(verifier.get("auditor_attempt_id") or ""),
        "generator_effective_seed": generator.get("effective_seed"),
        "verifier_effective_seed": verifier.get("effective_seed", verifier.get("seed")),
        "generator_input_digest": str(generator.get("input_digest") or ""),
        "generator_output_digest": str(generator.get("output_digest") or ""),
        "verifier_input_digest": str(verifier.get("input_digest") or ""),
        "verifier_output_digest": str(verifier.get("output_digest") or ""),
    }


def _structural_coverage(row: Mapping[str, Any]) -> dict[str, Any]:
    generator = _mapping(row.get("main_candidate_generator"))
    identity = _mapping(row.get("transaction_identity"))
    aggregations = row.get("claim_aggregation_events") or []
    return {
        "contract_id": "qasper_e2e_structural_coverage.v1",
        "message_stack": bool(generator.get("message_stack")),
        "raw_response": "raw_response" in generator,
        "finish_reason": bool(generator.get("finish_reason")),
        "typed_candidate_transform": bool(row.get("candidate_transformation_stages")),
        "claim_aggregation_before_after": bool(
            aggregations
            and all(
                "input_text" in event and "output_text" in event
                for event in aggregations
                if isinstance(event, Mapping)
            )
        ),
        "per_annotation_scores": bool(row.get("qasper_annotation_scores")),
        "transaction_identity": bool(
            identity.get("trace_group_id")
            and identity.get("generator_transaction_id")
            and identity.get("verifier_transaction_id")
        ),
        "candidate_verifier_audit": bool(
            _mapping(row.get("semantic_verifier")).get("candidate_verification_audit")
        ),
    }


def _online_model_coverage(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    audit = _mapping(verifier.get("candidate_verification_audit"))
    auditor_attempt_observed = _actual_auditor_attempt_observed(verifier, audit)
    return {
        "contract_id": "qasper_online_model_coverage.v1",
        "generator_model": str(generator.get("model") or ""),
        "generator_observed": bool(
            generator.get("model")
            and generator.get("finish_reason")
            and "raw_response" in generator
        ),
        "verifier_model": str(verifier.get("model") or ""),
        "verifier_observed": bool(
            verifier.get("model")
            and int(verifier.get("proposal_model_call_count") or 0) > 0
        ),
        "auditor_observed": auditor_attempt_observed,
        "auditor_attempt_observed": auditor_attempt_observed,
        "auditor_status": str(audit.get("status") or ""),
        "auditor_passed": audit.get("status") == "passed",
    }


def _actual_auditor_attempt_observed(
    verifier: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> bool:
    transaction_event = _latest_transaction_event(_mapping(verifier.get("debug_trace")))
    transaction = _mapping(transaction_event.get("transaction"))
    audit_stage = _mapping(transaction.get("audit"))
    attempts = audit_stage.get("attempts")
    attempt_observed = isinstance(attempts, list) and any(
        isinstance(attempt, Mapping)
        and bool(str(attempt.get("attempt_id") or "").strip())
        and (
            bool(str(attempt.get("raw_response") or ""))
            or bool(_mapping(attempt.get("parsed_value")))
        )
        for attempt in attempts
    )
    return bool(
        attempt_observed
        and int(verifier.get("audit_model_call_count") or 0) > 0
        and verifier.get("auditor_attempt_id")
        and str(audit.get("mode") or "") not in {"", "deterministic_schema_audit"}
        and audit.get("status") in {"passed", "failed"}
        and audit.get("audited_candidate") == verifier.get("candidate_label")
        and audit.get("audited_judgment")
        == verifier.get("candidate_verification_status")
        and audit.get("replacement_candidate_allowed") is False
    )


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


def _latest_transaction_event(
    debug_trace: Mapping[str, Any],
) -> dict[str, Any]:
    for event in reversed(debug_trace.get("events", []) or []):
        if not isinstance(event, Mapping) or event.get("event") != "model_transaction":
            continue
        if _mapping(event.get("transaction")):
            return dict(event)
    return {}


def _audited_typed_conclusion(
    verifier: Mapping[str, Any],
    transaction_event: Mapping[str, Any],
    rejected_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    transaction = _mapping(transaction_event.get("transaction"))
    proposal = _latest_parsed_value(transaction, "proposal")
    outcome = _mapping(transaction_event.get("outcome"))
    return _first_mapping(
        _latest_rejected_field(rejected_transactions, "typed_conclusion"),
        proposal.get("typed_conclusion"),
        outcome.get("typed_conclusion"),
        verifier.get("audited_typed_conclusion"),
        verifier.get("typed_conclusion"),
    )


def _audited_conclusion_audit(
    verifier: Mapping[str, Any],
    transaction_event: Mapping[str, Any],
    rejected_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    transaction = _mapping(transaction_event.get("transaction"))
    audit = _latest_parsed_value(transaction, "audit")
    outcome = _mapping(transaction_event.get("outcome"))
    return _first_mapping(
        _latest_rejected_field(rejected_transactions, "conclusion_audit"),
        audit.get("conclusion_audit"),
        audit.get("conclusion_check"),
        outcome.get("conclusion_audit"),
        verifier.get("conclusion_audit"),
    )


def _audited_polarity_check(
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
    rejected_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    return _first_mapping(
        _latest_rejected_field(
            rejected_transactions,
            "polarity_contradiction_check",
        ),
        verifier.get("polarity_contradiction_check"),
        authority.get("polarity_contradiction_check"),
    )


def _rejected_transactions(
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> list[dict[str, Any]]:
    values = [
        deepcopy(dict(value))
        for value in verifier.get("rejected_transactions", []) or []
        if isinstance(value, Mapping)
    ]
    if authority.get("audit_verified_but_runtime_rejected"):
        values.append(
            {
                "runtime_rejection_reason": authority.get("reason"),
                "proof_mode": authority.get("proof_mode"),
                "typed_conclusion": deepcopy(
                    authority.get("audited_typed_conclusion")
                    or authority.get("typed_conclusion")
                    or {}
                ),
                "conclusion_audit": deepcopy(
                    authority.get("audited_conclusion_audit")
                    or authority.get("conclusion_audit")
                    or {}
                ),
                "polarity_contradiction_check": deepcopy(
                    authority.get("polarity_contradiction_check") or {}
                ),
                "semantic_pack_digest": authority.get("semantic_pack_digest"),
            }
        )
    return values


def _latest_rejected_field(
    transactions: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    for transaction in reversed(transactions):
        value = _mapping(transaction.get(field))
        if value:
            return value
    return {}


def _latest_parsed_value(
    transaction: Mapping[str, Any],
    stage: str,
) -> dict[str, Any]:
    stage_value = _mapping(transaction.get(stage))
    for attempt in reversed(stage_value.get("attempts", []) or []):
        if not isinstance(attempt, Mapping):
            continue
        parsed_value = _mapping(attempt.get("parsed_value"))
        if parsed_value:
            return parsed_value
    return {}


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        mapped = _mapping(value)
        if mapped:
            return deepcopy(mapped)
    return {}


def _raw_audit_call_rejected(
    verifier: Mapping[str, Any],
    transaction_event: Mapping[str, Any],
) -> bool:
    if "audit_call_rejection_count" in verifier:
        return int(verifier.get("audit_call_rejection_count") or 0) > 0
    outcome = _mapping(transaction_event.get("outcome"))
    return str(verifier.get("audit_status") or outcome.get("audit_status") or "") == (
        "rejected"
    )


def _final_row_audit_rejected(
    verifier: Mapping[str, Any],
    transaction_event: Mapping[str, Any],
) -> bool:
    outcome = _mapping(transaction_event.get("outcome"))
    return str(verifier.get("status") or outcome.get("status") or "") == (
        "audit_rejected"
    )


def _audit_verified_but_runtime_rejected(
    verifier: Mapping[str, Any],
    authority: Mapping[str, Any],
    transaction_event: Mapping[str, Any],
) -> bool:
    if int(verifier.get("audit_verified_but_runtime_rejected_count") or 0) > 0:
        return True
    if authority.get("audit_verified_but_runtime_rejected") is True:
        return True
    audit_status = str(
        verifier.get("audit_status")
        or _mapping(transaction_event.get("outcome")).get("audit_status")
        or ""
    )
    return audit_status.startswith("verified") and (
        _final_row_audit_rejected(verifier, transaction_event)
        or authority.get("status") == "rejected"
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
