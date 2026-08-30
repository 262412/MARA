from __future__ import annotations

from typing import Any

from benchmark.qasper_semantic_state_matrix import qasper_candidate_bound_state_matrix
from scripts.slurm.qasper_debug_contract_audit import (  # noqa: F401
    _candidate_audit_complete,
    _known_evidence_ids,
    _nonempty_mapping_keys,
    _normalized_audited_premises,
    _premise_digest,
    _required_slot_state_unverified,
    _semantic_audit_failure_flags,
    _slot_ids,
    _string_set,
    _supported_row_required_slot_unverified,
    _typed_conclusion_present,
    _unknown_audit_premises_complete,
)
from scripts.slurm.qasper_debug_contract_causal import (
    causal_evidence_chain_complete as _causal_evidence_chain_complete,
)
from scripts.slurm.qasper_debug_contract_identity import (  # noqa: F401
    _digest,
    _normalized_candidate,
    _parse_candidate_response,
    _raw_candidate_attempt_valid,
    _raw_candidate_fields_present,
    _raw_candidate_fields_valid,
    _raw_candidate_identity_valid,
    _raw_candidate_output_valid,
    _raw_candidate_parts,
    _raw_candidate_stages_valid,
    _verifier_raw_identity_valid,
)
from scripts.slurm.qasper_debug_contract_lanes import (  # noqa: F401
    _lane_predictions,
    _lane_split_requested,
    qasper_debug_audit_extensions,
    qasper_debug_contract_metrics,
    qasper_debug_observability_coverage,
)
from scripts.slurm.qasper_debug_contract_lineage import (
    semantic_data_lineage_complete as _semantic_data_lineage_complete,
)
from scripts.slurm.qasper_debug_contract_recovery import (  # noqa: F401
    _answerable_false_abstention,
    _changed_digest,
    _recovery_transition_invalid,
    _reverify_events,
    _reverify_state_changed,
    _reverify_without_state_change_count,
    _semantic_recovery_transitions,
    _unchanged_digest,
)
from scripts.slurm.qasper_debug_contract_schema import (  # noqa: F401
    _audit_relation_consistent,
    _relation_flags_valid,
    _schema_audit_attempt_violations,
    _schema_debug_event_violations,
    _schema_proposal_attempt_violations,
    _schema_version_violations,
)
from scripts.slurm.qasper_debug_contract_semantic_pack import (
    canonical_semantic_pack_alignment_valid as _canonical_pack_alignment_valid,
)
from scripts.slurm.qasper_debug_contract_support import (  # noqa: F401
    _CANDIDATE_VERIFIER_AUDIT_CONTRACT,
    _CONCLUSION_AUDIT_CONTRACT,
    _GENERATOR_REQUIRED_FIELDS,
    _QASPER_CANDIDATE_GENERATION_CONTRACT,
    _QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
    _SEMANTIC_DEBUG_TRACE_CONTRACT,
    _SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
    _SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
    _SEMANTIC_VERIFIER_RUNTIME_CONTRACT,
    _VERIFIER_REQUIRED_FIELDS,
    _annotation_scores_complete,
    _audit_attempt_artifact_observed,
    _candidate_bound_auditor_attempt_observed,
    _candidate_bound_auditor_observed,
    _candidate_bound_auditor_passed,
    _candidate_proposition_binding_complete,
    _candidate_slot_binding_complete,
    _candidate_transform_complete,
    _empty_coverage_counts,
    _failed_auditor_safe_abstention,
    _input_output_digests_complete,
    _live_models_observed,
    _mapping,
    _require,
    _semantic_debug_audit_stage,
    _semantic_debug_complete,
    _semantic_stage_complete,
    _transaction_identity_complete,
    _verifier_observed,
    claim_aggregation_complete,
    terminal_metadata,
    terminal_semantic_answer,
)


def qasper_debug_behavior_violations(
    predictions: list[dict[str, Any]],
    contract_probe_predictions: list[dict[str, Any]] | None = None,
    *,
    quality_predictions: list[dict[str, Any]] | None = None,
) -> list[str]:
    violations: list[str] = []
    quality, probes = _lane_predictions(
        predictions,
        quality_predictions=quality_predictions,
        contract_probe_predictions=contract_probe_predictions,
    )
    split = _lane_split_requested(
        predictions,
        quality_predictions=quality_predictions,
        contract_probe_predictions=contract_probe_predictions,
    )
    for lane_predictions, lane in ((quality, "quality"), (probes, "contract_probe")):
        by_example: dict[str, list[dict[str, Any]]] = {}
        for prediction in lane_predictions:
            example_id = str(prediction.get("example_id") or "")
            by_example.setdefault(example_id, []).append(prediction)
            violations.extend(
                _prediction_violations(
                    prediction,
                    require_auditor=True,
                    require_causal_chain=lane == "quality",
                )
            )
        if lane == "quality":
            for example_id, rows in by_example.items():
                violations.extend(_cross_route_violations(example_id, rows))
    matrix = qasper_candidate_bound_state_matrix(
        predictions,
        contract_probe_predictions,
        quality_predictions=quality_predictions,
    )
    if split:
        if quality:
            violations.extend(_online_label_violations(matrix["quality_observation"]))
        if probes:
            violations.extend(
                _online_label_violations(matrix["contract_probe_observation"])
            )
    else:
        violations.extend(_online_label_violations(matrix["online_observation"]))
    return violations


def _online_label_violations(online: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if online["single_label_collapse"]:
        violations.append("candidate_single_label_collapse")
    if online["candidate_verifier_auditor_label_set_mismatch"]:
        violations.append("candidate_verifier_auditor_label_set_mismatch")
    for label in online["missing_required_candidate_labels"]:
        violations.append(f"online_required_candidate_label_missing:{label}")
    for label in online["missing_required_verifier_judgments"]:
        violations.append(f"online_required_verifier_judgment_missing:{label}")
    for label in online["missing_required_auditor_statuses"]:
        violations.append(f"online_required_auditor_status_missing:{label}")
    for label in online["missing_required_annotation_ambiguity_states"]:
        violations.append(f"online_annotation_ambiguity_missing:{label}")
    return violations


def _prediction_violations(
    prediction: dict[str, Any],
    *,
    require_auditor: bool = True,
    require_causal_chain: bool = True,
) -> list[str]:
    metadata = terminal_metadata(prediction)
    generator = _mapping(metadata.get("qasper_candidate_generation"))
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    candidate = str(generator.get("typed_candidate") or "")
    relation = str(verifier.get("candidate_verification_status") or "")
    prefix = f"{prediction.get('example_id')}:{prediction.get('route')}"
    violations = _generator_violations(generator, candidate, prefix)
    violations.extend(
        _verifier_violations(
            verifier,
            candidate,
            relation,
            prefix,
            require_auditor=require_auditor,
        )
    )
    _append_cross_stage_violations(
        violations,
        prediction,
        generator,
        verifier,
        prefix,
        require_causal_chain=require_causal_chain,
    )
    audit = _mapping(verifier.get("candidate_verification_audit"))
    if audit.get("status") == "failed":
        _require(
            violations,
            _failed_auditor_safe_abstention(verifier, prediction),
            f"failed_auditor_not_safely_abstained:{prefix}",
        )
    expected_terminal = (
        candidate
        if relation == "supported" and audit.get("status") == "passed"
        else "unanswerable"
    )
    _require(
        violations,
        terminal_semantic_answer(prediction) == expected_terminal,
        f"candidate_policy_terminal_mismatch:{prefix}",
    )
    _require(
        violations,
        _raw_candidate_identity_valid(generator, verifier),
        f"raw_candidate_identity_mismatch:{prefix}",
    )
    _require(
        violations,
        _candidate_audit_complete(verifier, audit),
        f"candidate_verifier_audit_empty:{prefix}",
    )
    return violations


def _append_cross_stage_violations(
    violations: list[str],
    prediction: dict[str, Any],
    generator: dict[str, Any],
    verifier: dict[str, Any],
    prefix: str,
    *,
    require_causal_chain: bool,
) -> None:
    _require(
        violations,
        generator.get("trace_group_id") == verifier.get("trace_group_id"),
        f"transaction_trace_group_mismatch:{prefix}",
    )
    _require(
        violations,
        generator.get("effective_seed") == verifier.get("effective_seed"),
        f"effective_seed_mismatch:{prefix}",
    )
    _require(
        violations,
        _canonical_pack_alignment_valid(prediction),
        f"canonical_semantic_pack_mismatch:{prefix}",
    )
    _require(
        violations,
        _live_models_observed(generator, verifier),
        f"online_model_coverage_missing:{prefix}",
    )
    _require(
        violations,
        _semantic_debug_complete(verifier),
        f"semantic_verifier_debug_incomplete:{prefix}",
    )
    _require(
        violations,
        _semantic_data_lineage_complete(verifier),
        f"semantic_data_lineage_incomplete:{prefix}",
    )
    if require_causal_chain:
        _require(
            violations,
            _causal_evidence_chain_complete(prediction),
            f"causal_evidence_chain_incomplete:{prefix}",
        )
    _require(
        violations,
        claim_aggregation_complete(prediction),
        f"claim_aggregation_diff_missing:{prefix}",
    )
    _require(
        violations,
        _annotation_scores_complete(prediction),
        f"annotation_score_coverage_missing:{prefix}",
    )


def _generator_violations(
    generator: dict[str, Any],
    candidate: str,
    prefix: str,
) -> list[str]:
    violations: list[str] = []
    _require(
        violations,
        generator.get("contract_id") == _QASPER_CANDIDATE_GENERATION_CONTRACT,
        f"generator_trace_missing:{prefix}",
    )
    _require(
        violations,
        generator.get("status") == "parsed",
        f"generator_candidate_not_parsed:{prefix}",
    )
    _require(
        violations,
        candidate in {"yes", "no", "unanswerable"},
        f"generator_candidate_invalid:{prefix}",
    )
    for field in _GENERATOR_REQUIRED_FIELDS:
        value = generator.get(field)
        _require(
            violations,
            field in generator and value is not None and value != "" and value != [],
            f"generator_field_missing:{field}:{prefix}",
        )
    _require(
        violations,
        "failure_reason" in generator,
        f"generator_failure_reason_missing:{prefix}",
    )
    _require(
        violations,
        _candidate_transform_complete(generator),
        f"candidate_transform_incomplete:{prefix}",
    )
    _require(
        violations,
        _candidate_proposition_binding_complete(generator),
        f"candidate_proposition_binding_invalid:{prefix}",
    )
    _require(
        violations,
        _raw_candidate_fields_present(generator),
        f"raw_candidate_identity_fields_missing:{prefix}",
    )
    return violations


def _verifier_violations(
    verifier: dict[str, Any],
    candidate: str,
    relation: str,
    prefix: str,
    *,
    require_auditor: bool = True,
) -> list[str]:
    violations: list[str] = []
    _require(
        violations,
        verifier.get("contract_id") == _SEMANTIC_VERIFIER_RUNTIME_CONTRACT,
        f"candidate_verifier_trace_missing:{prefix}",
    )
    _require(
        violations,
        str(verifier.get("candidate_label") or "") == candidate,
        f"candidate_identity_mismatch:{prefix}",
    )
    _require(
        violations,
        relation in {"supported", "contradicted", "unknown"},
        f"candidate_verifier_status_invalid:{prefix}",
    )
    _require(
        violations,
        verifier.get("replacement_candidate_allowed") is False,
        f"replacement_candidate_policy_invalid:{prefix}",
    )
    _require(
        violations,
        _relation_flags_valid(verifier, relation),
        f"candidate_relation_flags_invalid:{prefix}",
    )
    audit = _mapping(verifier.get("candidate_verification_audit"))
    _require(
        violations,
        audit.get("status") in {"passed", "failed"},
        f"candidate_verifier_audit_status_invalid:{prefix}",
    )
    _require(
        violations,
        audit.get("contract_id") == _CANDIDATE_VERIFIER_AUDIT_CONTRACT,
        f"candidate_verifier_audit_contract_invalid:{prefix}",
    )
    _require(
        violations,
        audit.get("audited_candidate") == candidate
        and audit.get("audited_judgment") == relation
        and audit.get("replacement_candidate_allowed") is False,
        f"candidate_verifier_audit_binding_invalid:{prefix}",
    )
    _require(
        violations,
        _audit_relation_consistent(verifier, relation),
        f"candidate_verifier_audit_relation_invalid:{prefix}",
    )
    for field in _VERIFIER_REQUIRED_FIELDS:
        value = verifier.get(field)
        _require(
            violations,
            field in verifier and value is not None and value != "",
            f"candidate_verifier_field_missing:{field}:{prefix}",
        )
    _require(
        violations,
        _live_models_observed({}, verifier),
        f"online_verifier_not_observed:{prefix}",
    )
    if require_auditor:
        _require(
            violations,
            _candidate_bound_auditor_observed(verifier),
            f"online_auditor_not_observed:{prefix}",
        )
    violations.extend(_schema_version_violations(verifier, prefix))
    return violations


def _cross_route_violations(
    example_id: str,
    rows: list[dict[str, Any]],
) -> list[str]:
    routes = {str(row.get("route") or "") for row in rows}
    generators = [
        _mapping(terminal_metadata(row).get("qasper_candidate_generation"))
        for row in rows
    ]
    group_ids = {str(value.get("trace_group_id") or "") for value in generators}
    transactions = {str(value.get("transaction_id") or "") for value in generators}
    verifiers = [
        _mapping(terminal_metadata(row).get("semantic_proposition_verifier"))
        for row in rows
    ]
    verifier_groups = {str(value.get("trace_group_id") or "") for value in verifiers}
    verifier_transactions = {
        str(value.get("transaction_id") or "") for value in verifiers
    }
    violations: list[str] = []
    _require(
        violations,
        len(rows) == 3 and len(routes) == 3,
        f"cross_route_coverage_incomplete:{example_id}",
    )
    _require(
        violations,
        len(group_ids) == 1 and group_ids == verifier_groups and "" not in group_ids,
        f"cross_route_trace_group_mismatch:{example_id}",
    )
    _require(
        violations,
        len(transactions) == 3 and "" not in transactions,
        f"cross_route_transaction_not_unique:{example_id}",
    )
    _require(
        violations,
        len(verifier_transactions) == 3 and "" not in verifier_transactions,
        f"cross_route_verifier_transaction_not_unique:{example_id}",
    )
    return violations
