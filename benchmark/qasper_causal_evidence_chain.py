from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.qasper_causal_evidence_chain_integrity import (
    candidate_input_state_complete as _candidate_input_state_complete,
)
from benchmark.qasper_causal_evidence_chain_integrity import (
    crosswalk_digest_matches as _crosswalk_digest_matches,
)
from benchmark.qasper_causal_evidence_chain_integrity import (
    digest_incompleteness_reasons as _digest_incompleteness_reasons,
)
from benchmark.qasper_causal_evidence_chain_integrity import (
    source_input_snapshot_complete as _source_input_snapshot_complete,
)
from benchmark.qasper_causal_evidence_chain_stages import (
    first_decisive_transition as _first_decisive_transition,
)
from benchmark.qasper_causal_evidence_chain_stages import stages as _build_stages
from benchmark.qasper_causal_evidence_chain_utils import (
    digest_matches as _digest_matches,
)
from benchmark.qasper_causal_evidence_chain_utils import is_sha256 as _sha256
from benchmark.qasper_causal_evidence_chain_utils import list_values as _list
from benchmark.qasper_causal_evidence_chain_utils import mapping as _mapping


def qasper_causal_evidence_chain(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build a fail-closed causal chain from recorded runtime observations."""

    generator = _mapping(row.get("main_candidate_generator"))
    verifier = _mapping(row.get("semantic_verifier"))
    lineage = _mapping(verifier.get("semantic_data_lineage"))
    source = _mapping(lineage.get("source_packing"))
    crosswalk = _mapping(source.get("selector_crosswalk"))
    construction = _mapping(lineage.get("plan_construction"))
    audit = _mapping(lineage.get("audit"))
    input_state = _mapping(row.get("candidate_input_state_observation"))
    reasons = _incompleteness_reasons(
        row,
        generator=generator,
        verifier=verifier,
        source=source,
        crosswalk=crosswalk,
        construction=construction,
        lineage=lineage,
        audit=audit,
        input_state=input_state,
    )
    status = "complete" if not reasons else "incomplete"
    first = (
        _first_decisive_transition(row, generator, verifier, lineage, construction)
        if not reasons
        else {
            "stage": "trace_contract",
            "decision": reasons[0],
            "classification": "causal_trace_incomplete",
        }
    )
    return {
        "contract_id": "qasper_causal_evidence_chain.v1",
        "status": status,
        "incompleteness_reasons": reasons,
        "first_decisive_transition": first,
        "stages": _stages(
            row,
            generator=generator,
            verifier=verifier,
            source=source,
            crosswalk=crosswalk,
            construction=construction,
            lineage=lineage,
            audit=audit,
            input_state=input_state,
        ),
    }


def qasper_causal_evidence_chain_prefix_complete(row: Mapping[str, Any]) -> bool:
    """Validate the recorded pre-model source-to-plan trace prefix."""

    generator = _mapping(row.get("main_candidate_generator"))
    verifier = _mapping(row.get("semantic_verifier"))
    lineage = _mapping(verifier.get("semantic_data_lineage"))
    source = _mapping(lineage.get("source_packing"))
    construction = _mapping(lineage.get("plan_construction"))
    crosswalk = _mapping(source.get("selector_crosswalk"))
    return bool(
        source.get("contract_id") == "qasper_source_packing_observation.v1"
        and _source_input_snapshot_complete(source)
        and _source_pipeline_decisions_complete(source)
        and _crosswalk_complete(crosswalk)
        and _source_selector_decisions_complete(source)
        and _canonical_selector_projection_complete(
            generator.get("canonical_selector_projection_trace")
        )
        and _candidate_decisions_complete(construction)
    )


def _incompleteness_reasons(
    row: Mapping[str, Any],
    *,
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    source: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    construction: Mapping[str, Any],
    lineage: Mapping[str, Any],
    audit: Mapping[str, Any],
    input_state: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if source.get("contract_id") != "qasper_source_packing_observation.v1":
        reasons.append("source_packing_observation_missing")
    if not _source_input_snapshot_complete(source):
        reasons.append("source_input_snapshot_incomplete")
    if not _source_pipeline_decisions_complete(source):
        reasons.append("source_or_window_decisions_incomplete")
    if not crosswalk:
        reasons.append("selector_crosswalk_missing")
    elif not _crosswalk_complete(crosswalk):
        reasons.append("selector_crosswalk_incomplete")
    if not _selector_decisions_complete(source):
        reasons.append("selector_decisions_incomplete")
    if not _canonical_selector_projection_complete(
        generator.get("canonical_selector_projection_trace")
    ):
        reasons.append("canonical_selector_projection_incomplete")
    if not _candidate_decisions_complete(construction):
        reasons.append("plan_candidate_decisions_incomplete")
    if not _generator_decision_complete(generator):
        reasons.append("generator_decision_incomplete")
    if not _candidate_input_state_complete(input_state, source):
        reasons.append("candidate_input_state_observation_incomplete")
    if not _record_projection_complete(
        generator.get("candidate_prompt_projection_trace"),
        contract_id="qasper_candidate_prompt_projection.v1",
    ):
        reasons.append("candidate_prompt_projection_incomplete")
    if not _record_projection_complete(
        generator.get("candidate_request_projection_trace"),
        contract_id="qasper_candidate_request_projection.v1",
    ):
        reasons.append("candidate_request_projection_incomplete")
    if not _plan_identity_projection_complete(
        generator, verifier, lineage, construction
    ):
        reasons.append("plan_identity_projection_incomplete")
    if not _attempts_complete(lineage.get("proposal_attempts")):
        reasons.append("proposal_attempt_lineage_incomplete")
    if not _attempts_complete(audit.get("attempts")):
        reasons.append("audit_attempt_lineage_incomplete")
    if not _decisive_transition_complete(lineage, construction, verifier):
        reasons.append("first_decisive_transition_missing")
    if not str(row.get("terminal_outcome") or ""):
        reasons.append("terminal_outcome_missing")
    if not _terminal_commit_complete(row):
        reasons.append("terminal_semantic_commit_incomplete")
    reasons.extend(
        _digest_incompleteness_reasons(
            generator=generator,
            verifier=verifier,
            source=source,
            crosswalk=crosswalk,
            construction=construction,
            lineage=lineage,
        )
    )
    return list(dict.fromkeys(reasons))


def _crosswalk_complete(crosswalk: Mapping[str, Any]) -> bool:
    canonical_count = int(crosswalk.get("canonical_selector_count") or 0)
    mapped_count = int(crosswalk.get("mapped_canonical_selector_count") or 0)
    rows = _list(crosswalk.get("canonical_selectors"))
    return bool(
        crosswalk.get("contract_id") == "qasper_selector_crosswalk.v1"
        and crosswalk.get("complete") is True
        and canonical_count > 0
        and mapped_count == canonical_count == len(rows)
        and _crosswalk_digest_matches(crosswalk)
        and all(_mapping(row).get("canonical_selector_ref") for row in rows)
    )


def _source_pipeline_decisions_complete(source: Mapping[str, Any]) -> bool:
    source_decisions = _list(source.get("source_decisions"))
    source_input_count = int(source.get("source_input_count") or 0)
    source_decision_count = int(source.get("source_decision_count") or 0)
    window_decisions = [
        _mapping(value) for value in _list(source.get("window_decisions"))
    ]
    window_selection_count = sum(
        decision.get("stage") == "window_selection" for decision in window_decisions
    )
    selected_window_count = sum(
        decision.get("stage") == "window_selection" and decision.get("selected") is True
        for decision in window_decisions
    )
    window_fit_count = sum(
        decision.get("stage") == "fit_to_input_budget" for decision in window_decisions
    )
    return bool(
        source.get("source_decisions_complete") is True
        and source_input_count > 0
        and source_decision_count == source_input_count == len(source_decisions)
        and _digest_matches(source_decisions, source.get("source_decisions_digest"))
        and all(_mapping(decision).get("reason") for decision in source_decisions)
        and all(
            not _mapping(decision).get("semantic_rank")
            or (
                _mapping(decision).get("priority")
                and _mapping(decision).get("priority_factors")
            )
            for decision in source_decisions
        )
        and source.get("window_decisions_complete") is True
        and window_selection_count
        == int(source.get("window_selection_decision_count") or 0)
        and selected_window_count == int(source.get("selected_window_count") or 0)
        and window_fit_count
        == int(source.get("window_fit_decision_count") or 0)
        == selected_window_count
        and len(window_decisions) == int(source.get("window_decision_count") or 0)
        and _digest_matches(window_decisions, source.get("window_decisions_digest"))
        and all(decision.get("reason") for decision in window_decisions)
    )


def _record_projection_complete(value: Any, *, contract_id: str) -> bool:
    trace = _mapping(value)
    decisions = _list(trace.get("decisions"))
    input_count = int(trace.get("input_record_count") or 0)
    decision_count = int(trace.get("decision_count") or 0)
    attempts = _list(trace.get("attempts"))
    return bool(
        trace.get("contract_id") == contract_id
        and trace.get("complete") is True
        and input_count > 0
        and decision_count == input_count == len(decisions)
        and _digest_matches(decisions, trace.get("decisions_digest"))
        and int(trace.get("attempt_count") or 0) == len(attempts)
        and _digest_matches(attempts, trace.get("attempts_digest"))
        and attempts
        and all(_mapping(decision).get("decision") for decision in decisions)
    )


def _selector_decisions_complete(source: Mapping[str, Any]) -> bool:
    source_records = _list(source.get("records"))
    canonical_records = _list(source.get("canonical_records")) or source_records
    source_complete = bool(source_records) and all(
        _projection_complete(
            _mapping(record).get("source_selector_projection_trace"),
        )
        for record in source_records
    )
    canonical_complete = bool(canonical_records) and all(
        _projection_complete(
            _mapping(record).get("candidate_selector_projection_trace"),
        )
        for record in canonical_records
    )
    return source_complete and canonical_complete


def _source_selector_decisions_complete(source: Mapping[str, Any]) -> bool:
    records = _list(source.get("records"))
    return bool(records) and all(
        _projection_complete(_mapping(record).get("source_selector_projection_trace"))
        for record in records
    )


def _projection_complete(value: Any) -> bool:
    trace = _mapping(value)
    decisions = _list(trace.get("decisions"))
    input_count = int(
        trace.get("input_selector_count") or trace.get("input_span_count") or 0
    )
    decision_count = int(trace.get("decision_count") or 0)
    return bool(
        trace.get("complete") is True
        and input_count > 0
        and decision_count == input_count == len(decisions)
        and _digest_matches(decisions, trace.get("decisions_digest"))
        and all(_mapping(decision).get("decision") for decision in decisions)
    )


def _canonical_selector_projection_complete(value: Any) -> bool:
    trace = _mapping(value)
    decisions = _list(trace.get("decisions"))
    input_count = int(trace.get("input_selector_count") or 0)
    return bool(
        trace.get("contract_id") == "qasper_canonical_selector_projection.v1"
        and trace.get("complete") is True
        and input_count > 0
        and int(trace.get("decision_count") or 0) == input_count == len(decisions)
        and _digest_matches(decisions, trace.get("decisions_digest"))
        and all(
            _mapping(decision).get("decision") in {"selected", "rejected"}
            and _mapping(decision).get("reason")
            for decision in decisions
        )
    )


def _candidate_decisions_complete(construction: Mapping[str, Any]) -> bool:
    decisions = _list(construction.get("candidate_decisions"))
    selector_decisions = _list(construction.get("selector_pool_decisions"))
    decision_count = int(construction.get("candidate_decision_count") or 0)
    analysis_count = int(construction.get("relation_analysis_count") or 0)
    return bool(
        construction.get("enumeration_policy_complete") is True
        and _digest_matches(
            construction.get("enumeration_policy"),
            construction.get("enumeration_policy_digest"),
        )
        and _mapping(construction.get("enumeration_policy"))
        and construction.get("selector_pool_decisions_complete") is True
        and int(construction.get("selector_pool_decision_count") or 0)
        == len(selector_decisions)
        and _digest_matches(
            selector_decisions,
            construction.get("selector_pool_decisions_digest"),
        )
        and construction.get("candidate_decisions_complete") is True
        and analysis_count > 0
        and decision_count == analysis_count == len(decisions)
        and _digest_matches(
            decisions,
            construction.get("candidate_decisions_digest"),
        )
        and all(
            _mapping(decision).get("candidate_id")
            and _mapping(decision).get("relation")
            and _mapping(decision).get("origin")
            and _mapping(decision).get("decision") in {"accepted", "rejected"}
            and (
                _mapping(decision).get("decision") == "accepted"
                or bool(_mapping(decision).get("rejection_reasons"))
            )
            for decision in decisions
        )
    )


def _generator_decision_complete(generator: Mapping[str, Any]) -> bool:
    decision = _mapping(generator.get("model_decision"))
    context = _mapping(decision.get("decision_context"))
    return bool(
        generator.get("status") == "parsed"
        and generator.get("typed_candidate") in {"yes", "no", "unanswerable"}
        and decision.get("contract_id") == "qasper_model_candidate_decision.v1"
        and decision.get("status") == "parsed"
        and decision.get("decision") == generator.get("typed_candidate")
        and decision.get("decision_origin") == "model_output"
        and decision.get("rationale_status") == "not_requested_by_low_entropy_contract"
        and context.get("decision_plan_alignment")
        in {
            "aligned_no_legal_local_plan",
            "conflicts_with_legal_local_plan",
            "candidate_without_legal_local_plan",
            "locally_plan_eligible",
        }
        and _sha256(context.get("plan_candidate_decisions_digest"))
        and _digest_matches(context, decision.get("decision_context_digest"))
        and decision.get("raw_response_digest") == generator.get("raw_response_digest")
        and _sha256(generator.get("input_digest"))
        and _sha256(generator.get("output_digest"))
    )


def _plan_identity_projection_complete(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> bool:
    projection = _plan_identity_projection(generator, verifier, lineage, construction)
    return projection["status"] == "complete"


def _plan_identity_projection(
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> dict[str, Any]:
    binding = _mapping(generator.get("candidate_evidence_set_binding"))
    parent = _mapping(binding.get("canonical_evidence_plan"))
    child_ids = sorted(
        str(_mapping(parent.get(key)).get("plan_id") or "")
        for key in ("support_plan", "contradiction_plan")
        if str(_mapping(parent.get(key)).get("plan_id") or "")
    )
    expected_allowed = {
        "relation_bound_support": [
            str(_mapping(parent.get("support_plan")).get("plan_id") or "")
        ],
        "relation_bound_contradiction": [
            str(_mapping(parent.get("contradiction_plan")).get("plan_id") or "")
        ],
    }.get(str(binding.get("binding_state") or ""), [])
    expected_allowed = sorted(plan_id for plan_id in expected_allowed if plan_id)
    allowed_ids = sorted(
        str(plan_id)
        for plan_id in _list(
            _mapping(lineage.get("proposal_contract")).get("allowed_plan_ids")
        )
        if str(plan_id)
    )
    local_plan_id = str(
        _mapping(lineage.get("local_projection")).get("selected_plan_id") or ""
    )
    construction_plan_id = str(construction.get("selected_plan_id") or "")
    rejected_ids = sorted(
        str(_mapping(rejected).get("canonical_evidence_plan_id") or "")
        for rejected in _list(verifier.get("rejected_transactions"))
        if str(_mapping(rejected).get("canonical_evidence_plan_id") or "")
    )
    parent_id = str(parent.get("plan_id") or "")
    selected_ids = [
        plan_id for plan_id in (local_plan_id, construction_plan_id) if plan_id
    ]
    identifiers_valid = bool(
        parent.get("contract_id") == "canonical_proposition_evidence_plan.v2"
        and _sha256(parent_id)
        and all(_sha256(plan_id) for plan_id in child_ids)
    )
    projection_consistent = bool(
        allowed_ids == expected_allowed
        and local_plan_id == construction_plan_id
        and all(plan_id in allowed_ids for plan_id in selected_ids)
        and all(plan_id == local_plan_id for plan_id in rejected_ids)
        and (
            rejected_ids == [local_plan_id]
            if str(verifier.get("audit_status") or "") in {"failed", "rejected"}
            and local_plan_id
            else True
        )
        and (int(construction.get("legal_plan_count") or 0) == len(expected_allowed))
    )
    return {
        "status": (
            "complete" if identifiers_valid and projection_consistent else "incomplete"
        ),
        "parent_plan_id": parent_id,
        "constituent_plan_ids": child_ids,
        "binding_state": str(binding.get("binding_state") or ""),
        "expected_allowed_plan_ids": expected_allowed,
        "allowed_plan_ids": allowed_ids,
        "local_selected_plan_id": local_plan_id,
        "construction_selected_plan_id": construction_plan_id,
        "auditor_rejected_plan_ids": rejected_ids,
    }


def _attempts_complete(value: Any) -> bool:
    attempts = _list(value)
    return bool(
        attempts
        and all(
            int(_mapping(attempt).get("attempt") or 0) > 0
            and (
                _sha256(_mapping(attempt).get("raw_response_digest"))
                or bool(_mapping(attempt).get("provider_failure_reason"))
            )
            for attempt in attempts
        )
    )


def _terminal_commit_complete(row: Mapping[str, Any]) -> bool:
    commit = _mapping(row.get("terminal_semantic_commit"))
    return bool(
        commit.get("contract_id") == "terminal_semantic_commit.v3"
        and commit.get("outcome") == row.get("terminal_outcome")
        and commit.get("answer_status") == row.get("answer_status")
        and commit.get("semantic_answer") in {"yes", "no", "unanswerable"}
        and _sha256(commit.get("projection_hash"))
    )


def _decisive_transition_complete(
    lineage: Mapping[str, Any],
    construction: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> bool:
    transition = _mapping(lineage.get("first_decisive_transition"))
    identity_complete = bool(
        transition.get("stage")
        and transition.get("decision")
        and _sha256(transition.get("observation_digest"))
        and _mapping(transition.get("decision_context"))
        and _digest_matches(
            transition.get("decision_context"),
            transition.get("decision_context_digest"),
        )
    )
    if not identity_complete:
        return False
    if int(construction.get("legal_plan_count") or 0) == 0:
        return bool(
            transition.get("stage") == "plan_construction"
            and transition.get("decision") == "no_legal_evidence_plan"
        )
    if transition.get("stage") == "candidate_generation":
        context = _mapping(transition.get("decision_context"))
        return bool(
            transition.get("decision") == "unanswerable_despite_legal_local_plan"
            and context.get("candidate") == "unanswerable"
            and int(context.get("legal_plan_count") or 0) > 0
        )
    if (
        transition.get("stage") == "auditor_semantics"
        and verifier.get("audit_status") == "candidate_bound"
    ):
        context = _mapping(transition.get("decision_context"))
        return bool(
            transition.get("decision") == "candidate_bound"
            and context.get("audit_status") == "candidate_bound"
            and verifier.get("audit_status") == "candidate_bound"
        )
    inconsistency = _mapping(lineage.get("first_inconsistency"))
    if inconsistency:
        return bool(
            transition.get("stage") == inconsistency.get("stage")
            and transition.get("decision") == inconsistency.get("reason")
        )
    return transition.get("stage") == "terminal_semantic_commit"


def _stages(
    row: Mapping[str, Any],
    *,
    generator: Mapping[str, Any],
    verifier: Mapping[str, Any],
    source: Mapping[str, Any],
    crosswalk: Mapping[str, Any],
    construction: Mapping[str, Any],
    lineage: Mapping[str, Any],
    audit: Mapping[str, Any],
    input_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return _build_stages(
        row,
        generator=generator,
        verifier=verifier,
        source=source,
        crosswalk=crosswalk,
        construction=construction,
        lineage=lineage,
        audit=audit,
        input_state=input_state,
        source_pipeline_complete=_source_pipeline_decisions_complete,
        crosswalk_complete=_crosswalk_complete,
        canonical_selector_projection_complete=_canonical_selector_projection_complete,
        candidate_decisions_complete=_candidate_decisions_complete,
        record_projection_complete=_record_projection_complete,
        plan_identity_projection=_plan_identity_projection,
    )
