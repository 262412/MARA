from __future__ import annotations

from typing import Any

from benchmark.qasper_semantic_state_matrix import (
    qasper_candidate_bound_state_matrix,
    split_qasper_debug_predictions,
)
from scripts.slurm.qasper_debug_contract_audit import (
    _candidate_audit_complete,
    _required_slot_state_unverified,
    _semantic_audit_failure_flags,
    _supported_row_required_slot_unverified,
    _typed_conclusion_present,
)
from scripts.slurm.qasper_debug_contract_identity import _raw_candidate_identity_valid
from scripts.slurm.qasper_debug_contract_metric_payload import (
    metric_payload as _metric_payload,
)
from scripts.slurm.qasper_debug_contract_observability import (
    qasper_debug_observability_coverage,
)
from scripts.slurm.qasper_debug_contract_recovery import (
    _answerable_false_abstention,
    _reverify_without_state_change_count,
)
from scripts.slurm.qasper_debug_contract_support import (
    _candidate_bound_auditor_attempt_observed,
    _mapping,
    _verifier_observed,
    terminal_metadata,
)


def qasper_debug_audit_extensions(
    predictions: list[dict[str, Any]],
    contract_probe_predictions: list[dict[str, Any]] | None = None,
    *,
    quality_predictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    quality, probes = _lane_predictions(
        predictions,
        quality_predictions=quality_predictions,
        contract_probe_predictions=contract_probe_predictions,
    )
    lane_audits = {
        "quality_audit": _lane_audit(
            quality,
            lane="quality",
            contract_probe_predictions=[],
        ),
        "contract_probe_audit": _lane_audit(
            probes,
            lane="contract_probe",
            contract_probe_predictions=probes,
        ),
    }
    return {
        "observability_coverage": qasper_debug_observability_coverage(
            quality,
            require_auditor=True,
        ),
        "combined_observability_coverage": qasper_debug_observability_coverage(
            [*quality, *probes],
            require_auditor=True,
        ),
        "contract_probe_observability_coverage": lane_audits["contract_probe_audit"][
            "observability_coverage"
        ],
        "structural_state_matrix": qasper_candidate_bound_state_matrix(
            predictions,
            contract_probe_predictions,
            quality_predictions=quality_predictions,
        ),
        "debug_gate_metrics": qasper_debug_contract_metrics(
            predictions,
            contract_probe_predictions,
            quality_predictions=quality_predictions,
        ),
        **lane_audits,
        "quality_lane": lane_audits["quality_audit"],
        "contract_probe_lane": lane_audits["contract_probe_audit"],
        "contract_probe_artifact": _contract_probe_artifact(
            probes,
            explicit=contract_probe_predictions is not None,
            audit=lane_audits["contract_probe_audit"],
        ),
    }


def _contract_probe_artifact(
    probes: list[dict[str, Any]],
    *,
    explicit: bool,
    audit: dict[str, Any],
) -> dict[str, Any]:
    if probes:
        source = (
            "explicit_live_prediction_rows" if explicit else "embedded_live_lane_rows"
        )
        status = str(audit.get("status") or "failed")
    else:
        source = "missing_live_prediction_rows"
        status = "missing"
    return {
        "embedded_in": "contract_smoke_audit.json",
        "source": source,
        "prediction_count": len(probes),
        "non_vacuous": bool(probes),
        "covered_state_cell_count": int(audit.get("covered_state_cell_count") or 0),
        "separate_live_prediction_artifact_required": True,
        "status": status,
    }


def _lane_audit(
    predictions: list[dict[str, Any]],
    *,
    lane: str,
    contract_probe_predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    coverage = qasper_debug_observability_coverage(
        predictions,
        require_auditor=True,
    )
    matrix = qasper_candidate_bound_state_matrix(
        predictions,
        contract_probe_predictions,
        quality_predictions=predictions if lane == "quality" else [],
    )
    metrics = qasper_debug_contract_metrics(
        predictions,
        contract_probe_predictions,
        quality_predictions=predictions if lane == "quality" else [],
        lane=lane,
    )
    observation = matrix[
        "quality_observation" if lane == "quality" else "contract_probe_observation"
    ]
    if lane == "quality":
        complete = bool(
            predictions
            and coverage["complete"]
            and metrics["qasper_quality_answerable_row_count"] > 0
            and metrics["answerable_false_abstention_count"] == 0
            and metrics["qasper_online_auditor_attempt_missing_count"] == 0
            and not observation["missing_required_candidate_labels"]
        )
    else:
        complete = _live_probe_complete(
            predictions,
            coverage=coverage,
            observation=observation,
            metrics=metrics,
        )
    return {
        "lane": lane,
        "required": lane == "contract_probe",
        "execution": "live_model_rows"
        if lane == "contract_probe"
        else "live_quality_rows",
        "prediction_count": len(predictions),
        "live_prediction_count": len(predictions),
        "non_vacuous": bool(predictions),
        "status": "passed" if complete else "missing" if not predictions else "failed",
        "covered_state_cell_count": observation["observed_state_cell_count"],
        "live_state_matrix_complete": (
            observation.get("state_matrix_complete", False)
            if lane == "contract_probe"
            else None
        ),
        "observability_coverage": coverage,
        "structural_state_matrix": matrix,
        "debug_gate_metrics": metrics,
    }


def _live_probe_complete(
    predictions: list[dict[str, Any]],
    *,
    coverage: dict[str, Any],
    observation: dict[str, Any],
    metrics: dict[str, float],
) -> bool:
    return bool(
        predictions
        and coverage["complete"]
        and not observation.get("missing_required_candidate_labels")
        and not observation.get("missing_required_verifier_judgments")
        and not observation.get("missing_required_auditor_statuses")
        and metrics["qasper_online_auditor_attempt_missing_count"] == 0.0
        and metrics["qasper_online_verifier_missing_count"] == 0.0
        and metrics["qasper_unexpected_unknown_assessment_count"] == 0.0
    )


def _lane_predictions(
    predictions: list[dict[str, Any]],
    *,
    quality_predictions: list[dict[str, Any]] | None,
    contract_probe_predictions: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if contract_probe_predictions is not None:
        quality = (
            list(predictions)
            if quality_predictions is None
            else list(quality_predictions)
        )
        return quality, list(contract_probe_predictions)
    if quality_predictions is not None:
        return list(quality_predictions), []
    return split_qasper_debug_predictions(predictions)


def _lane_split_requested(
    predictions: list[dict[str, Any]],
    *,
    quality_predictions: list[dict[str, Any]] | None,
    contract_probe_predictions: list[dict[str, Any]] | None,
) -> bool:
    if quality_predictions is not None or contract_probe_predictions is not None:
        return True
    lane_values = {
        "quality",
        "real",
        "quality_audit",
        "contract_probe",
        "probe",
        "synthetic",
        "negative",
    }
    for prediction in predictions:
        for source in (
            prediction,
            _mapping(prediction.get("example_metadata")),
            _mapping(prediction.get("evidence_metadata")),
        ):
            if any(
                str(source.get(field) or "").strip().casefold() in lane_values
                for field in _lane_marker_fields()
            ) or any(
                source.get(field) is True
                for field in ("contract_probe", "synthetic_contract_probe")
            ):
                return True
    return False


def _lane_marker_fields() -> tuple[str, ...]:
    return (
        "qasper_debug_lane",
        "contract_probe_lane",
        "contract_smoke_lane",
        "debug_lane",
    )


def qasper_debug_contract_metrics(
    predictions: list[dict[str, Any]],
    contract_probe_predictions: list[dict[str, Any]] | None = None,
    *,
    quality_predictions: list[dict[str, Any]] | None = None,
    lane: str = "combined",
) -> dict[str, float]:
    """Return fail-closed metrics specific to the online QASPER debug task."""

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
    matrix = qasper_candidate_bound_state_matrix(
        predictions,
        contract_probe_predictions,
        quality_predictions=quality_predictions,
    )
    quality_observation = matrix["quality_observation"]
    probe_observation = matrix["contract_probe_observation"]
    counts = _metric_counts([*quality, *probes], quality)
    quality_counts = _metric_counts(quality, quality)
    probe_counts = _metric_counts(probes, [])
    probe_counts["unexpected_false_abstentions"] = sum(
        int(_answerable_false_abstention(prediction))
        for prediction in probes
        if not _expected_negative_probe(prediction)
    )
    quality_label, probe_label = _metric_label_observations(
        matrix,
        lane=lane,
        split=split,
        probes_present=bool(probes),
    )
    flags = _metric_label_flags(quality_label, probe_label)
    quality_flags = _metric_label_flags(
        quality_observation, _empty_online_observation()
    )
    probe_flags = _metric_label_flags(_empty_online_observation(), probe_observation)
    return _metric_payload(
        counts,
        flags,
        quality_flags=quality_flags,
        probe_flags=probe_flags,
        quality_counts=quality_counts,
        probe_counts=probe_counts,
        quality_count=len(quality),
        probe_count=len(probes),
        probe_observation=matrix["contract_probe_observation"],
        structural_matrix_complete=bool(matrix["complete"]),
    )


def _metric_counts(
    all_predictions: list[dict[str, Any]],
    quality: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {
        "raw_identity_mismatches": 0,
        "empty_audits": 0,
        "empty_typed_conclusions": 0,
        "entailment_failures": 0,
        "entailment_rejections": 0,
        "supported_slot_unverified": 0,
        "answerable_slot_unverified": 0,
        "false_abstentions": 0,
        "reverify_without_state_change": 0,
        "auditor_attempt_missing": 0,
        "verifier_missing": 0,
        "answerable_rows": 0,
        "required_slot_overlap": 0,
        "unexpected_unknown_assessment": 0,
    }
    for prediction in all_predictions:
        metadata = terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        audit = _mapping(verifier.get("candidate_verification_audit"))
        counts["raw_identity_mismatches"] += int(
            not _raw_candidate_identity_valid(generator, verifier)
        )
        counts["empty_audits"] += int(not _candidate_audit_complete(verifier, audit))
        counts["empty_typed_conclusions"] += int(
            audit.get("status") == "passed"
            and not _typed_conclusion_present(verifier, audit)
        )
        audit_failure, audit_rejection = _semantic_audit_failure_flags(
            verifier,
            audit,
            prediction,
        )
        counts["entailment_failures"] += int(audit_failure)
        counts["entailment_rejections"] += int(audit_rejection)
        counts["supported_slot_unverified"] += int(
            _supported_row_required_slot_unverified(verifier, audit, metadata)
        )
        counts["reverify_without_state_change"] += _reverify_without_state_change_count(
            prediction
        )
        counts["auditor_attempt_missing"] += int(
            not _candidate_bound_auditor_attempt_observed(verifier)
        )
        counts["verifier_missing"] += int(not _verifier_observed(verifier))
        counts["unexpected_unknown_assessment"] += _unexpected_unknown_assessment_count(
            verifier
        )
    _add_quality_metric_counts(counts, quality)
    return counts


def _add_quality_metric_counts(
    counts: dict[str, int],
    quality: list[dict[str, Any]],
) -> None:
    for prediction in quality:
        metadata = terminal_metadata(prediction)
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        audit = _mapping(verifier.get("candidate_verification_audit"))
        supported_missing = _supported_row_required_slot_unverified(
            verifier,
            audit,
            metadata,
        )
        answerable = _answerable_prediction(prediction)
        answerable_missing = answerable and _answerable_row_required_slot_unverified(
            prediction,
            verifier,
            audit,
            metadata,
        )
        counts["answerable_rows"] += int(answerable)
        counts["answerable_slot_unverified"] += int(answerable_missing)
        counts["required_slot_overlap"] += int(supported_missing and answerable_missing)
        counts["false_abstentions"] += int(_answerable_false_abstention(prediction))


def _metric_label_observations(
    matrix: dict[str, Any],
    *,
    lane: str,
    split: bool,
    probes_present: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    empty = _empty_online_observation()
    if lane == "quality":
        return matrix["quality_observation"], empty
    if lane == "contract_probe":
        return empty, matrix["contract_probe_observation"]
    if split:
        probe = matrix["contract_probe_observation"] if probes_present else empty
        return matrix["quality_observation"], probe
    online = matrix["online_observation"]
    return online, online


def _metric_label_flags(
    quality_label: dict[str, Any],
    probe_label: dict[str, Any],
) -> dict[str, bool]:
    return {
        "label_mismatch": bool(
            quality_label["candidate_verifier_auditor_label_set_mismatch"]
            or probe_label["candidate_verifier_auditor_label_set_mismatch"]
        ),
        "missing_candidate_labels": bool(
            quality_label["missing_required_candidate_labels"]
            or probe_label["missing_required_candidate_labels"]
        ),
        "missing_verifier_judgments": bool(
            probe_label["missing_required_verifier_judgments"]
        ),
        "missing_auditor_statuses": bool(
            probe_label["missing_required_auditor_statuses"]
        ),
        "missing_ambiguity_states": bool(
            probe_label["missing_required_annotation_ambiguity_states"]
        ),
    }


def _empty_online_observation() -> dict[str, Any]:
    return {
        "candidate_verifier_auditor_label_set_mismatch": False,
        "missing_required_candidate_labels": [],
        "missing_required_verifier_judgments": [],
        "missing_required_auditor_statuses": [],
        "missing_required_annotation_ambiguity_states": [],
    }


def _unexpected_unknown_assessment_count(verifier: dict[str, Any]) -> int:
    debug = _mapping(verifier.get("debug_trace"))
    count = 0
    for event in debug.get("events") or []:
        if not isinstance(event, dict) or event.get("event") != "model_transaction":
            continue
        transaction = _mapping(event.get("transaction"))
        proposal = _mapping(transaction.get("proposal"))
        for attempt in proposal.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            if str(attempt.get("parse_failure_reason") or "") == (
                "unexpected_unknown_assessment"
            ):
                count += 1
    return count


def _expected_negative_probe(prediction: dict[str, Any]) -> bool:
    for source in (
        prediction,
        _mapping(prediction.get("example_metadata")),
        _mapping(prediction.get("evidence_metadata")),
    ):
        if source.get("expected_negative_probe") is True:
            return True
        if str(source.get("contract_probe_expectation") or "").strip().casefold() in {
            "auditor_fail",
            "expected_auditor_fail",
        }:
            return True
    return False


def _answerable_prediction(prediction: dict[str, Any]) -> bool:
    return any(
        str(answer or "").strip().casefold() in {"yes", "no", "true", "false"}
        for answer in prediction.get("gold_answers") or []
    )


def _answerable_row_required_slot_unverified(
    prediction: dict[str, Any],
    verifier: dict[str, Any],
    audit: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    if not _answerable_prediction(prediction):
        return False
    return _supported_row_required_slot_unverified(verifier, audit, metadata) or (
        verifier.get("candidate_verification_status") != "supported"
        and _required_slot_state_unverified(verifier, audit, metadata)
    )
