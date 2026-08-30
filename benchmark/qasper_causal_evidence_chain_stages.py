from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from benchmark.qasper_causal_evidence_chain_utils import list_values, mapping


def first_decisive_transition(
    row: Mapping[str, Any],
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> dict[str, str]:
    recorded = mapping(lineage.get("first_decisive_transition"))
    ambiguous = (
        mapping(row.get("qasper_annotation_diagnostics")).get("ambiguous") is True
    )
    if int(construction.get("legal_plan_count") or 0) == 0:
        return _unresolved_transition(recorded, ambiguous)
    if recorded.get("stage") == "candidate_generation":
        return _candidate_transition(recorded)
    if (
        recorded.get("stage") == "auditor_semantics"
        and verifier.get("audit_status") == "candidate_bound"
    ):
        return _candidate_bound_transition(recorded)
    first = mapping(lineage.get("first_inconsistency"))
    if first:
        return _inconsistent_transition(recorded, first)
    if generator.get("status") != "parsed":
        return {
            "stage": "candidate_generation",
            "decision": str(generator.get("failure_reason") or "generation_failed"),
            "classification": "execution_failure",
        }
    if str(verifier.get("audit_status") or "") in {"failed", "rejected"}:
        return {
            "stage": "auditor_semantics",
            "decision": str(verifier.get("audit_reason") or "audit_rejected"),
            "classification": "unexpected_semantic_rejection",
        }
    return _terminal_transition(row, recorded)


def _unresolved_transition(
    recorded: Mapping[str, Any],
    ambiguous: bool,
) -> dict[str, str]:
    return {
        "stage": str(recorded.get("stage") or "plan_construction"),
        "decision": str(recorded.get("decision") or "no_legal_evidence_plan"),
        "classification": (
            "expected_ambiguity_unresolved" if ambiguous else "unexpected_unresolved"
        ),
        "observation_digest": str(recorded.get("observation_digest") or ""),
        "decision_context_digest": str(recorded.get("decision_context_digest") or ""),
    }


def _candidate_transition(recorded: Mapping[str, Any]) -> dict[str, str]:
    return {
        "stage": "candidate_generation",
        "decision": str(recorded.get("decision") or "candidate_plan_conflict"),
        "classification": "unexpected_candidate_decision",
        "observation_digest": str(recorded.get("observation_digest") or ""),
        "decision_context_digest": str(recorded.get("decision_context_digest") or ""),
    }


def _candidate_bound_transition(recorded: Mapping[str, Any]) -> dict[str, str]:
    return {
        "stage": "auditor_semantics",
        "decision": "candidate_bound",
        "classification": "candidate_bound_abstention",
        "observation_digest": str(recorded.get("observation_digest") or ""),
        "decision_context_digest": str(recorded.get("decision_context_digest") or ""),
    }


def _inconsistent_transition(
    recorded: Mapping[str, Any],
    first: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "stage": str(
            recorded.get("stage") or first.get("stage") or "transaction_runtime"
        ),
        "decision": str(
            recorded.get("decision") or first.get("reason") or "semantic_inconsistency"
        ),
        "classification": "unexpected_semantic_rejection",
        "observation_digest": str(recorded.get("observation_digest") or ""),
        "decision_context_digest": str(recorded.get("decision_context_digest") or ""),
    }


def _terminal_transition(
    row: Mapping[str, Any],
    recorded: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "stage": str(recorded.get("stage") or "terminal_semantic_commit"),
        "decision": str(
            recorded.get("decision") or row.get("terminal_outcome") or "committed"
        ),
        "classification": "terminal_outcome",
        "observation_digest": str(recorded.get("observation_digest") or ""),
        "decision_context_digest": str(recorded.get("decision_context_digest") or ""),
    }


def stages(
    row: Mapping[str, Any],
    *,
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    source: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    construction: Mapping[str, Any],
    lineage: Mapping[str, Any],
    audit: Mapping[str, Any],
    source_pipeline_complete: Callable[[Mapping[str, Any]], bool],
    crosswalk_complete: Callable[[Mapping[str, Any]], bool],
    canonical_selector_projection_complete: Callable[[Any], bool],
    candidate_decisions_complete: Callable[[Mapping[str, Any]], bool],
    record_projection_complete: Callable[..., bool],
    plan_identity_projection: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _source_stage(source),
        _window_stage(source, source_pipeline_complete),
        _selector_stage(
            generator,
            crosswalk,
            crosswalk_complete,
            canonical_selector_projection_complete,
        ),
        _plan_stage(construction, candidate_decisions_complete),
        _generation_stage(generator, record_projection_complete),
        _identity_stage(
            generator,
            verifier,
            lineage,
            construction,
            plan_identity_projection,
        ),
        _selection_stage(lineage, construction),
        _auditor_stage(audit, verifier),
        _recovery_stage(row, verifier, lineage),
        _terminal_stage(row),
    ]


def _source_stage(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": "source_packing",
        "status": str(source.get("status") or "missing"),
        "input_count": len(list_values(source.get("source_records"))),
        "output_count": len(list_values(source.get("records"))),
        "identity_digest": str(source.get("source_semantic_pack_digest") or ""),
        "decision_digest": str(source.get("source_decisions_digest") or ""),
    }


def _window_stage(
    source: Mapping[str, Any],
    source_pipeline_complete: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any]:
    return {
        "stage": "window_selection_and_fit",
        "status": "complete" if source_pipeline_complete(source) else "incomplete",
        "selection_decision_count": int(
            source.get("window_selection_decision_count") or 0
        ),
        "selected_window_count": int(source.get("selected_window_count") or 0),
        "fit_decision_count": int(source.get("window_fit_decision_count") or 0),
        "identity_digest": str(source.get("window_decisions_digest") or ""),
    }


def _selector_stage(
    generator: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    crosswalk_complete: Callable[[Mapping[str, Any]], bool],
    canonical_selector_projection_complete: Callable[[Any], bool],
) -> dict[str, Any]:
    return {
        "stage": "selector_projection",
        "status": "complete" if crosswalk_complete(crosswalk) else "incomplete",
        "input_count": int(crosswalk.get("source_selector_count") or 0),
        "output_count": int(crosswalk.get("canonical_selector_count") or 0),
        "identity_digest": str(crosswalk.get("crosswalk_digest") or ""),
        "canonical_projection_status": (
            "complete"
            if canonical_selector_projection_complete(
                generator.get("canonical_selector_projection_trace")
            )
            else "incomplete"
        ),
    }


def _plan_stage(
    construction: Mapping[str, Any],
    candidate_decisions_complete: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any]:
    return {
        "stage": "plan_construction",
        "status": (
            "complete" if candidate_decisions_complete(construction) else "incomplete"
        ),
        "input_count": int(construction.get("candidate_count") or 0),
        "output_count": int(construction.get("legal_plan_count") or 0),
        "identity_digest": str(construction.get("candidate_decisions_digest") or ""),
    }


def _generation_stage(
    generator: Mapping[str, Any],
    record_projection_complete: Callable[..., bool],
) -> dict[str, Any]:
    return {
        "stage": "candidate_generation",
        "status": str(generator.get("status") or "missing"),
        "decision": str(generator.get("typed_candidate") or ""),
        "input_digest": str(generator.get("input_digest") or ""),
        "output_digest": str(generator.get("output_digest") or ""),
        "prompt_projection_status": (
            "complete"
            if record_projection_complete(
                generator.get("candidate_prompt_projection_trace"),
                contract_id="qasper_candidate_prompt_projection.v1",
            )
            else "incomplete"
        ),
        "request_projection_status": (
            "complete"
            if record_projection_complete(
                generator.get("candidate_request_projection_trace"),
                contract_id="qasper_candidate_request_projection.v1",
            )
            else "incomplete"
        ),
    }


def _identity_stage(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
    plan_identity_projection: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    return {
        "stage": "plan_identity_projection",
        **plan_identity_projection(generator, verifier, lineage, construction),
    }


def _selection_stage(
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "stage": "plan_selection",
        "status": str(mapping(lineage.get("local_projection")).get("status") or ""),
        "selected_plan_id": str(construction.get("selected_plan_id") or ""),
        "attempt_count": len(list_values(lineage.get("proposal_attempts"))),
    }


def _auditor_stage(
    audit: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "stage": "auditor",
        "status": str(audit.get("status") or verifier.get("audit_status") or ""),
        "decision": str(verifier.get("audit_reason") or audit.get("reason") or ""),
        "decision_class": audit_decision_class(audit, verifier),
        "attempt_count": len(list_values(audit.get("attempts"))),
    }


def _recovery_stage(
    row: Mapping[str, Any],
    verifier: Mapping[str, Any],
    lineage: Mapping[str, Any],
) -> dict[str, Any]:
    transitions = recovery_rows(row, verifier)
    first = mapping(lineage.get("first_decisive_transition"))
    return {
        "stage": "recovery",
        "status": "observed" if transitions else "not_run",
        "transition_count": len(transitions),
        "cause_stage": str(first.get("stage") or ""),
        "cause_observation_digest": str(first.get("observation_digest") or ""),
    }


def _terminal_stage(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": "terminal",
        "status": str(row.get("answer_status") or ""),
        "decision": str(row.get("terminal_outcome") or ""),
        "identity_digest": str(
            mapping(row.get("terminal_semantic_commit")).get("projection_hash") or ""
        ),
    }


def audit_decision_class(
    audit: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> str:
    attempts = [mapping(value) for value in list_values(audit.get("attempts"))]
    if any(attempt.get("provider_failure_reason") for attempt in attempts):
        return "provider_failure"
    if any(attempt.get("parse_failure_reason") for attempt in attempts):
        return "parser_failure"
    semantic_status = str(verifier.get("audit_status") or "")
    if semantic_status in {"failed", "rejected"}:
        return "semantic_rejection"
    if semantic_status == "candidate_bound":
        return "candidate_bound"
    if semantic_status in {"passed", "verified"}:
        return "semantic_acceptance"
    return "unknown"


def recovery_rows(
    row: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> list[Any]:
    transitions = list_values(row.get("recovery_transitions"))
    if not transitions:
        transitions = list_values(verifier.get("recovery_transitions"))
    return [*list_values(row.get("recovery_events")), *transitions]
