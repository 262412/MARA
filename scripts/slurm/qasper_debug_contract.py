from __future__ import annotations

from typing import Any


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
        fields["finish_reason"] += int(bool(generator.get("finish_reason")))
        fields["typed_candidate_transform"] += int(
            bool(generator.get("transformation_stages"))
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
        fields["candidate_verifier_audit"] += int(
            _mapping(verifier.get("candidate_verification_audit")).get("status")
            == "passed"
        )
        fields["semantic_verifier_debug"] += int(_semantic_debug_complete(verifier))
        fields["live_model"] += int(_live_models_observed(generator, verifier))
    total = len(predictions)
    return {
        "contract_id": "qasper_e2e_observability_coverage.v1",
        "prediction_count": total,
        "covered_counts": fields,
        "complete": bool(total and all(value == total for value in fields.values())),
    }


def claim_aggregation_complete(prediction: dict[str, Any]) -> bool:
    events = [
        event
        for event in prediction.get("controller_trace") or []
        if isinstance(event, dict) and event.get("stage") == "claim_aggregation"
    ]
    return bool(
        events
        and all(
            event.get("input_digest")
            and event.get("output_digest")
            and "input_text" in event
            and "output_text" in event
            for event in events
        )
    )


def terminal_metadata(prediction: dict[str, Any]) -> dict[str, Any]:
    bundle = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    metadata = _mapping(bundle.get("metadata"))
    return metadata or _mapping(prediction.get("evidence_metadata"))


def terminal_semantic_answer(prediction: dict[str, Any]) -> str:
    commit = _mapping(prediction.get("terminal_semantic_commit"))
    return (
        str(
            commit.get("semantic_answer")
            or prediction.get("engine_terminal_answer")
            or ""
        )
        .strip()
        .casefold()
    )


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
    expected_terminal = candidate if relation == "supported" else "unanswerable"
    _require(
        violations,
        terminal_semantic_answer(prediction) == expected_terminal,
        f"candidate_policy_terminal_mismatch:{prefix}",
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
        generator.get("contract_id") == "qasper_typed_candidate_generation.v1",
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
        verifier.get("contract_id") == "semantic_proposition_verifier_runtime.v2",
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
    audit = _mapping(verifier.get("candidate_verification_audit"))
    _require(
        violations,
        audit.get("status") == "passed",
        f"candidate_verifier_audit_failed:{prefix}",
    )
    _require(
        violations,
        audit.get("audited_candidate") == candidate
        and audit.get("audited_judgment") == relation
        and audit.get("replacement_candidate_allowed") is False,
        f"candidate_verifier_audit_binding_invalid:{prefix}",
    )
    for field in _VERIFIER_REQUIRED_FIELDS:
        _require(
            violations,
            field in verifier and verifier.get(field) not in {None, ""},
            f"candidate_verifier_field_missing:{field}:{prefix}",
        )
    _require(
        violations,
        _live_models_observed({}, verifier),
        f"online_verifier_not_observed:{prefix}",
    )
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


def _annotation_scores_complete(prediction: dict[str, Any]) -> bool:
    annotations = prediction.get("qasper_annotation_scores")
    annotations = annotations if isinstance(annotations, list) else []
    expected = _mapping(prediction.get("example_metadata")).get(
        "qasper_answer_annotations"
    )
    expected = expected if isinstance(expected, list) else []
    diagnostics = _mapping(prediction.get("qasper_annotation_diagnostics"))
    required_score_fields = {
        "annotation_index",
        "answer_f1",
        "typed_accuracy",
        "evidence_f1",
        "ambiguity_marker",
    }
    scores_complete = bool(annotations) and all(
        isinstance(score, dict)
        and score.get("contract_id") == "qasper_annotation_score.v1"
        and required_score_fields <= set(score)
        for score in annotations
    )
    diagnostics_complete = bool(
        diagnostics.get("contract_id") == "qasper_annotation_diagnostics.v1"
        and diagnostics.get("annotation_count") == len(expected)
        and isinstance(diagnostics.get("ambiguous"), bool)
        and isinstance(diagnostics.get("ambiguity_reasons"), list)
        and isinstance(diagnostics.get("canonical_answer_classes"), list)
    )
    return (
        scores_complete and diagnostics_complete and len(annotations) == len(expected)
    )


def _candidate_transform_complete(generator: dict[str, Any]) -> bool:
    stages = generator.get("transformation_stages")
    stages = stages if isinstance(stages, list) else []
    by_name = {
        str(stage.get("stage") or ""): stage
        for stage in stages
        if isinstance(stage, dict)
    }
    required = ("raw_response", "cleaning", "typed_candidate")
    if any(name not in by_name for name in required):
        return False
    common_fields = {"value", "digest", "failure_reason"}
    return bool(
        all(common_fields <= set(by_name[name]) for name in required)
        and "changed" in by_name["cleaning"]
    )


def _semantic_debug_complete(verifier: dict[str, Any]) -> bool:
    debug = _mapping(verifier.get("debug_trace"))
    if debug.get("contract_id") != "semantic_proposition_debug_trace.v2":
        return False
    transactions = [
        event
        for event in debug.get("events") or []
        if isinstance(event, dict) and event.get("event") == "model_transaction"
    ]
    if not transactions:
        return False
    transaction = _mapping(transactions[-1].get("transaction"))
    proposal = _mapping(transaction.get("proposal"))
    audit = _mapping(transaction.get("audit"))
    if not _semantic_stage_complete(proposal, allow_not_run=False):
        return False
    return _semantic_stage_complete(audit, allow_not_run=True)


def _semantic_stage_complete(stage: dict[str, Any], *, allow_not_run: bool) -> bool:
    if allow_not_run and stage.get("status") == "not_run":
        return True
    attempts = stage.get("attempts")
    attempts = attempts if isinstance(attempts, list) else []
    required_fields = {
        "attempt",
        "raw_response",
        "finish_reason",
        "parse_failure_reason",
        "provider_failure_reason",
    }
    return bool(
        attempts
        and all(
            isinstance(attempt, dict)
            and required_fields <= set(attempt)
            and bool(attempt.get("raw_response"))
            for attempt in attempts
        )
    )


def _transaction_identity_complete(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    return bool(
        generator.get("trace_group_id")
        and generator.get("trace_group_id") == verifier.get("trace_group_id")
        and generator.get("transaction_id")
        and generator.get("attempt_id")
        and verifier.get("transaction_id")
        and verifier.get("attempt_id")
    )


def _input_output_digests_complete(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    return bool(
        generator.get("input_digest")
        and generator.get("output_digest")
        and verifier.get("input_digest")
        and verifier.get("output_digest")
    )


def _live_models_observed(
    generator: dict[str, Any],
    verifier: dict[str, Any],
) -> bool:
    generator_observed = not generator or bool(generator.get("model"))
    return bool(
        generator_observed
        and verifier.get("model")
        and int(verifier.get("proposal_model_call_count") or 0) > 0
    )


def _empty_coverage_counts() -> dict[str, int]:
    return {
        "generator_trace": 0,
        "raw_response": 0,
        "finish_reason": 0,
        "typed_candidate_transform": 0,
        "claim_aggregation_before_after": 0,
        "per_annotation_scores": 0,
        "transaction_attempt_identity": 0,
        "effective_seed": 0,
        "input_output_digest": 0,
        "candidate_verifier_audit": 0,
        "semantic_verifier_debug": 0,
        "live_model": 0,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _require(violations: list[str], condition: bool, violation: str) -> None:
    if not condition:
        violations.append(violation)


_GENERATOR_REQUIRED_FIELDS = (
    "message_stack",
    "raw_response",
    "cleaned_response",
    "finish_reason",
    "transformation_stages",
    "trace_group_id",
    "transaction_id",
    "attempt_id",
    "effective_seed",
    "input_digest",
    "output_digest",
)

_VERIFIER_REQUIRED_FIELDS = (
    "trace_group_id",
    "transaction_id",
    "attempt_id",
    "auditor_attempt_id",
    "effective_seed",
    "input_digest",
    "output_digest",
)
