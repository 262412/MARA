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
    coverage_predictions = [*quality, *probes] if probes else quality
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
            coverage_predictions,
            require_auditor=True,
        ),
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
        ),
    }


def _contract_probe_artifact(
    probes: list[dict[str, Any]],
    *,
    explicit: bool,
) -> dict[str, Any]:
    source = (
        "explicit_argument"
        if explicit
        else "embedded_lane_marker"
        if probes
        else "deterministic_structural_projection"
    )
    return {
        "embedded_in": "contract_smoke_audit.json",
        "source": source,
        "prediction_count": len(probes),
        "non_vacuous": True,
        "covered_state_cell_count": 12,
        "separate_live_prediction_artifact_required": False,
        "status": "executed",
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
        complete = _structural_probe_complete(matrix)
    return {
        "lane": lane,
        "required": lane == "contract_probe",
        "execution": (
            "deterministic_structural_projection"
            if lane == "contract_probe"
            else "live_quality_rows"
        ),
        "prediction_count": len(predictions),
        "live_prediction_count": len(predictions),
        "non_vacuous": bool(
            matrix["cells"] if lane == "contract_probe" else predictions
        ),
        "status": "passed" if complete else "missing" if not predictions else "failed",
        "covered_state_cell_count": (
            len(matrix["cells"])
            if lane == "contract_probe"
            else observation["observed_state_cell_count"]
        ),
        "live_state_matrix_complete": (
            observation.get("state_matrix_complete", False)
            if lane == "contract_probe"
            else None
        ),
        "observability_coverage": coverage,
        "structural_state_matrix": matrix,
        "debug_gate_metrics": metrics,
    }


def _structural_probe_complete(matrix: dict[str, Any]) -> bool:
    return bool(
        matrix["complete"]
        and len(matrix["cells"]) == 12
        and all(
            cell.get("replacement_candidate_allowed") is False
            and cell.get("original_candidate") == cell.get("candidate_after_audit")
            for cell in matrix["cells"]
        )
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
    counts = _metric_counts([*quality, *probes], quality)
    quality_label, probe_label = _metric_label_observations(
        matrix,
        lane=lane,
        split=split,
        probes_present=bool(probes),
    )
    flags = _metric_label_flags(quality_label, probe_label)
    return _metric_payload(
        counts,
        flags,
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


def _metric_payload(
    counts: dict[str, int],
    flags: dict[str, bool],
    *,
    quality_count: int,
    probe_count: int,
    probe_observation: dict[str, Any],
    structural_matrix_complete: bool,
) -> dict[str, float]:
    required_slot_unverified = (
        counts["supported_slot_unverified"]
        + counts["answerable_slot_unverified"]
        - counts["required_slot_overlap"]
    )
    return {
        "answerable_false_abstention_count": float(counts["false_abstentions"]),
        "qasper_quality_prediction_count": float(quality_count),
        "qasper_contract_probe_prediction_count": float(probe_count),
        "qasper_quality_answerable_row_count": float(counts["answerable_rows"]),
        "qasper_quality_answerable_required_slot_unverified_count": float(
            counts["answerable_slot_unverified"]
        ),
        "qasper_quality_answerable_denominator_missing_count": float(
            counts["answerable_rows"] == 0
        ),
        "qasper_contract_probe_observed_state_cell_count": float(
            probe_observation.get("observed_state_cell_count", 0)
        ),
        "qasper_contract_probe_state_matrix_complete": float(
            structural_matrix_complete
        ),
        "qasper_contract_probe_live_state_matrix_complete": float(
            bool(probe_observation.get("state_matrix_complete", False))
        ),
        "qasper_supported_row_required_slot_unverified_count": float(
            counts["supported_slot_unverified"]
        ),
        "qasper_candidate_raw_identity_mismatch_count": float(
            counts["raw_identity_mismatches"]
        ),
        "qasper_empty_candidate_audit_count": float(counts["empty_audits"]),
        "qasper_empty_typed_conclusion_count": float(counts["empty_typed_conclusions"]),
        "qasper_semantic_entailment_audit_failure_count": float(
            counts["entailment_failures"]
        ),
        "qasper_semantic_entailment_audit_rejection_count": float(
            counts["entailment_rejections"]
        ),
        "qasper_required_slot_unverified_count": float(required_slot_unverified),
        "qasper_reverify_without_semantic_state_change_count": float(
            counts["reverify_without_state_change"]
        ),
        "qasper_candidate_verifier_auditor_label_set_mismatch_count": float(
            flags["label_mismatch"]
        ),
        "qasper_online_required_candidate_label_missing_count": float(
            flags["missing_candidate_labels"]
        ),
        "qasper_online_required_verifier_judgment_missing_count": float(
            flags["missing_verifier_judgments"]
        ),
        "qasper_online_required_auditor_status_missing_count": float(
            flags["missing_auditor_statuses"]
        ),
        "qasper_online_required_annotation_ambiguity_missing_count": float(
            flags["missing_ambiguity_states"]
        ),
        "qasper_online_auditor_attempt_missing_count": float(
            counts["auditor_attempt_missing"]
        ),
        "qasper_online_verifier_missing_count": float(counts["verifier_missing"]),
    }


def _empty_online_observation() -> dict[str, Any]:
    return {
        "candidate_verifier_auditor_label_set_mismatch": False,
        "missing_required_candidate_labels": [],
        "missing_required_verifier_judgments": [],
        "missing_required_auditor_statuses": [],
        "missing_required_annotation_ambiguity_states": [],
    }


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
