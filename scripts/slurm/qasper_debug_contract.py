from __future__ import annotations

from typing import Any

from benchmark.qasper_semantic_state_matrix import qasper_candidate_bound_state_matrix
from scripts.slurm.qasper_debug_contract_audit import (  # noqa: F401
    _candidate_audit_complete,
    _known_evidence_ids,
    _nonempty_mapping_keys,
    _normalized_audited_premises,
    _premise_digest,
    _semantic_audit_failure_flags,
    _slot_ids,
    _string_set,
    _supported_row_required_slot_unverified,
    _typed_conclusion_present,
    _unknown_audit_premises_complete,
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
    _relation_flags_valid,
    _schema_audit_attempt_violations,
    _schema_debug_event_violations,
    _schema_proposal_attempt_violations,
    _schema_version_violations,
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
    claim_aggregation_complete,
    terminal_metadata,
    terminal_semantic_answer,
)


def qasper_debug_audit_extensions(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "observability_coverage": qasper_debug_observability_coverage(predictions),
        "structural_state_matrix": qasper_candidate_bound_state_matrix(predictions),
        "debug_gate_metrics": qasper_debug_contract_metrics(predictions),
    }


def qasper_debug_behavior_violations(
    predictions: list[dict[str, Any]],
) -> list[str]:
    violations: list[str] = []
    by_example: dict[str, list[dict[str, Any]]] = {}
    for prediction in predictions:
        example_id = str(prediction.get("example_id") or "")
        by_example.setdefault(example_id, []).append(prediction)
        violations.extend(_prediction_violations(prediction))
    for example_id, rows in by_example.items():
        violations.extend(_cross_route_violations(example_id, rows))
    online = qasper_candidate_bound_state_matrix(predictions)["online_observation"]
    violations.extend(_online_label_violations(online))
    return violations


def qasper_debug_contract_metrics(
    predictions: list[dict[str, Any]],
) -> dict[str, float]:
    """Return fail-closed metrics specific to the online QASPER debug task."""

    matrix = qasper_candidate_bound_state_matrix(predictions)
    online = matrix["online_observation"]
    raw_identity_mismatches = 0
    empty_audits = 0
    empty_typed_conclusions = 0
    entailment_failures = 0
    entailment_rejections = 0
    required_slot_unverified = 0
    false_abstentions = 0
    reverify_without_state_change = 0
    auditor_attempt_missing = 0
    for prediction in predictions:
        metadata = terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        audit = _mapping(verifier.get("candidate_verification_audit"))
        raw_identity_mismatches += int(
            not _raw_candidate_identity_valid(generator, verifier)
        )
        empty_audits += int(not _candidate_audit_complete(verifier, audit))
        empty_typed_conclusions += int(
            audit.get("status") == "passed"
            and not _typed_conclusion_present(verifier, audit)
        )
        audit_failure, audit_rejection = _semantic_audit_failure_flags(
            verifier, audit, prediction
        )
        entailment_failures += int(audit_failure)
        entailment_rejections += int(audit_rejection)
        required_slot_unverified += int(
            _supported_row_required_slot_unverified(verifier, audit, metadata)
        )
        false_abstentions += int(_answerable_false_abstention(prediction))
        reverify_without_state_change += _reverify_without_state_change_count(
            prediction
        )
        auditor_attempt_missing += int(
            not _candidate_bound_auditor_attempt_observed(verifier)
        )
    return {
        "answerable_false_abstention_count": float(false_abstentions),
        "qasper_candidate_raw_identity_mismatch_count": float(raw_identity_mismatches),
        "qasper_empty_candidate_audit_count": float(empty_audits),
        "qasper_empty_typed_conclusion_count": float(empty_typed_conclusions),
        "qasper_semantic_entailment_audit_failure_count": float(entailment_failures),
        "qasper_semantic_entailment_audit_rejection_count": float(
            entailment_rejections
        ),
        "qasper_required_slot_unverified_count": float(required_slot_unverified),
        "qasper_reverify_without_semantic_state_change_count": float(
            reverify_without_state_change
        ),
        "qasper_candidate_verifier_auditor_label_set_mismatch_count": float(
            online["candidate_verifier_auditor_label_set_mismatch"]
        ),
        "qasper_online_required_candidate_label_missing_count": float(
            bool(online["missing_required_candidate_labels"])
        ),
        "qasper_online_required_verifier_judgment_missing_count": float(
            bool(online["missing_required_verifier_judgments"])
        ),
        "qasper_online_required_auditor_status_missing_count": float(
            bool(online["missing_required_auditor_statuses"])
        ),
        "qasper_online_required_annotation_ambiguity_missing_count": float(
            bool(online["missing_required_annotation_ambiguity_states"])
        ),
        "qasper_online_auditor_attempt_missing_count": float(auditor_attempt_missing),
    }


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


def qasper_debug_observability_coverage(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    fields = _empty_coverage_counts()
    for prediction in predictions:
        metadata = terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        fields["generator_trace"] += int(bool(generator))
        fields["raw_response"] += int("raw_response" in generator)
        fields["raw_candidate_identity"] += int(
            _raw_candidate_identity_valid(generator, verifier)
        )
        fields["finish_reason"] += int(bool(generator.get("finish_reason")))
        fields["typed_candidate_transform"] += int(
            bool(generator.get("transformation_stages"))
        )
        fields["proposition_slot_binding"] += int(
            _candidate_proposition_binding_complete(generator)
        )
        fields["claim_aggregation_before_after"] += int(
            claim_aggregation_complete(prediction)
        )
        fields["per_annotation_scores"] += int(
            bool(prediction.get("qasper_annotation_scores"))
        )
        fields["transaction_attempt_identity"] += int(
            _transaction_identity_complete(generator, verifier)
        )
        fields["effective_seed"] += int(
            generator.get("effective_seed") is not None
            and generator.get("effective_seed") == verifier.get("effective_seed")
        )
        fields["input_output_digest"] += int(
            _input_output_digests_complete(generator, verifier)
        )
        fields["auditor_attempt_observed"] += int(
            _candidate_bound_auditor_attempt_observed(verifier)
        )
        fields["candidate_verifier_audit"] += int(
            _candidate_bound_auditor_passed(verifier)
        )
        fields["auditor_failed_safe_abstention"] += int(
            _failed_auditor_safe_abstention(verifier, prediction)
        )
        fields["semantic_verifier_debug"] += int(_semantic_debug_complete(verifier))
        fields["live_model"] += int(_live_models_observed(generator, verifier))
    total = len(predictions)
    auditor_outcome_coverage = (
        fields["candidate_verifier_audit"] + fields["auditor_failed_safe_abstention"]
    )
    required_fields = {
        key: value
        for key, value in fields.items()
        if key
        not in {
            "candidate_verifier_audit",
            "auditor_failed_safe_abstention",
        }
    }
    return {
        "contract_id": "qasper_e2e_observability_coverage.v1",
        "prediction_count": total,
        "covered_counts": fields,
        "auditor_outcome_coverage": auditor_outcome_coverage,
        "complete": bool(
            total
            and all(value == total for value in required_fields.values())
            and auditor_outcome_coverage == total
        ),
    }


def _prediction_violations(prediction: dict[str, Any]) -> list[str]:
    metadata = terminal_metadata(prediction)
    generator = _mapping(metadata.get("qasper_candidate_generation"))
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    candidate = str(generator.get("typed_candidate") or "")
    relation = str(verifier.get("candidate_verification_status") or "")
    prefix = f"{prediction.get('example_id')}:{prediction.get('route')}"
    violations = _generator_violations(generator, candidate, prefix)
    violations.extend(_verifier_violations(verifier, candidate, relation, prefix))
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
        claim_aggregation_complete(prediction),
        f"claim_aggregation_diff_missing:{prefix}",
    )
    _require(
        violations,
        _annotation_scores_complete(prediction),
        f"annotation_score_coverage_missing:{prefix}",
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
