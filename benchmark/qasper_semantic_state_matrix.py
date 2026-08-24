from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

STATE_MATRIX_CONTRACT = "qasper_candidate_bound_state_matrix.v1"
_JUDGMENTS = ("supported", "contradicted", "unknown")
_AUDITOR_STATUSES = ("passed", "failed")
_AMBIGUITY_STATES = (False, True)
_CANDIDATE_LABELS = ("yes", "no", "unanswerable")
_REQUIRED_ONLINE_CANDIDATE_LABELS = ("no",)
_REQUIRED_ONLINE_VERIFIER_JUDGMENTS = ("contradicted", "unknown")
_REQUIRED_ONLINE_AUDITOR_STATUSES = ("failed", "passed")
_REQUIRED_ONLINE_ANNOTATION_STATES = ("ambiguous", "unambiguous")
_QUALITY_LANE = "quality"
_CONTRACT_PROBE_LANE = "contract_probe"


def split_qasper_debug_predictions(
    predictions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate real quality rows from explicitly marked contract probes."""

    quality: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    for prediction in predictions:
        if _prediction_lane(prediction) == _CONTRACT_PROBE_LANE:
            probes.append(prediction)
        else:
            quality.append(prediction)
    return quality, probes


def _prediction_lane(prediction: Mapping[str, Any]) -> str:
    for source in (
        prediction,
        _mapping(prediction.get("example_metadata")),
        _mapping(prediction.get("evidence_metadata")),
    ):
        for field in (
            "qasper_debug_lane",
            "contract_probe_lane",
            "contract_smoke_lane",
            "debug_lane",
        ):
            value = str(source.get(field) or "").strip().casefold()
            if value in {"contract_probe", "probe", "synthetic", "negative"}:
                return _CONTRACT_PROBE_LANE
            if value in {"quality", "real", "quality_audit"}:
                return _QUALITY_LANE
        for field in ("contract_probe", "synthetic_contract_probe"):
            if source.get(field) is True:
                return _CONTRACT_PROBE_LANE
    return _QUALITY_LANE


def qasper_candidate_bound_state_matrix(
    predictions: list[dict[str, Any]],
    contract_probe_predictions: list[dict[str, Any]] | None = None,
    *,
    quality_predictions: list[dict[str, Any]] | None = None,
    probe_predictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project the immutable-candidate contract separately from live coverage."""

    if contract_probe_predictions is None:
        contract_probe_predictions = probe_predictions
    if quality_predictions is None and contract_probe_predictions is None:
        (
            quality_predictions,
            contract_probe_predictions,
        ) = split_qasper_debug_predictions(predictions)
    elif quality_predictions is None:
        quality_predictions = list(predictions)
    elif contract_probe_predictions is None:
        contract_probe_predictions = []
    assert quality_predictions is not None
    assert contract_probe_predictions is not None
    combined = [*quality_predictions, *contract_probe_predictions]
    has_probe_rows = bool(contract_probe_predictions)

    cells = [
        _matrix_cell(judgment, auditor_status, ambiguous)
        for judgment in _JUDGMENTS
        for auditor_status in _AUDITOR_STATUSES
        for ambiguous in _AMBIGUITY_STATES
    ]
    return {
        "contract_id": STATE_MATRIX_CONTRACT,
        "matrix_kind": "structural_contract_projection",
        "auditor_scope": "original_candidate_and_verifier_judgment_only",
        "replacement_candidate_allowed": False,
        "required_dimensions": {
            "verifier_judgment": list(_JUDGMENTS),
            "auditor_status": list(_AUDITOR_STATUSES),
            "annotation_ambiguous": list(_AMBIGUITY_STATES),
        },
        "cells": cells,
        "complete": _matrix_complete(cells),
        "online_observation": _online_observation(
            combined,
            lane="legacy" if has_probe_rows else _QUALITY_LANE,
        ),
        "legacy_online_observation": _online_observation(combined),
        "quality_observation": _online_observation(
            quality_predictions,
            lane=_QUALITY_LANE,
        ),
        "contract_probe_observation": _online_observation(
            contract_probe_predictions,
            lane=_CONTRACT_PROBE_LANE,
        ),
        "lane_split": {
            "quality_prediction_count": len(quality_predictions),
            "contract_probe_prediction_count": len(contract_probe_predictions),
            "combined_prediction_count": len(combined),
            "contract_probe_rows_present": has_probe_rows,
        },
    }


def _matrix_cell(
    judgment: str,
    auditor_status: str,
    annotation_ambiguous: bool,
) -> dict[str, Any]:
    authority_eligible = judgment == "supported" and auditor_status == "passed"
    return {
        "case_id": (
            f"{judgment}:{auditor_status}:"
            f"{'ambiguous' if annotation_ambiguous else 'unambiguous'}"
        ),
        "original_candidate": "yes",
        "verifier_judgment": judgment,
        "auditor_status": auditor_status,
        "annotation_ambiguous": annotation_ambiguous,
        "audited_candidate": "yes",
        "candidate_after_audit": "yes",
        "replacement_candidate_allowed": False,
        "explicit_contradiction": judgment == "contradicted",
        "candidate_verifier_disagreement": judgment == "contradicted",
        "unknown": judgment == "unknown",
        "authority_eligible": authority_eligible,
        "terminal_action": (
            "accept_original_candidate" if authority_eligible else "safe_abstention"
        ),
        "annotation_effect": (
            "scoring_ambiguous" if annotation_ambiguous else "scoring_unambiguous"
        ),
    }


def _matrix_complete(cells: list[dict[str, Any]]) -> bool:
    observed = {
        (
            cell.get("verifier_judgment"),
            cell.get("auditor_status"),
            cell.get("annotation_ambiguous"),
        )
        for cell in cells
    }
    expected = {
        (judgment, auditor_status, ambiguous)
        for judgment in _JUDGMENTS
        for auditor_status in _AUDITOR_STATUSES
        for ambiguous in _AMBIGUITY_STATES
    }
    return observed == expected and all(_cell_invariants_hold(cell) for cell in cells)


def _cell_invariants_hold(cell: Mapping[str, Any]) -> bool:
    judgment = cell.get("verifier_judgment")
    auditor_status = cell.get("auditor_status")
    eligible = judgment == "supported" and auditor_status == "passed"
    return bool(
        cell.get("replacement_candidate_allowed") is False
        and cell.get("original_candidate") == cell.get("audited_candidate")
        and cell.get("original_candidate") == cell.get("candidate_after_audit")
        and cell.get("explicit_contradiction") == (judgment == "contradicted")
        and cell.get("candidate_verifier_disagreement") == (judgment == "contradicted")
        and cell.get("unknown") == (judgment == "unknown")
        and cell.get("authority_eligible") == eligible
        and cell.get("terminal_action")
        == ("accept_original_candidate" if eligible else "safe_abstention")
    )


def _online_observation(
    predictions: list[dict[str, Any]],
    *,
    lane: str = "legacy",
) -> dict[str, Any]:
    counters, expected_annotation_labels = _online_counters(predictions)
    (
        candidates,
        verifier_candidates,
        auditor_candidates,
        judgments,
        auditor_statuses,
        ambiguity,
    ) = counters
    observed_candidates = _observed_label_set(candidates)
    observed_verifier_candidates = _observed_label_set(verifier_candidates)
    observed_auditor_candidates = _observed_label_set(auditor_candidates)
    observed_judgments = _recognized_labels(judgments, _JUDGMENTS)
    observed_auditor_statuses = _recognized_labels(auditor_statuses, _AUDITOR_STATUSES)
    observed_ambiguity = _recognized_labels(ambiguity, ("ambiguous", "unambiguous"))
    exact = bool(
        observed_candidates
        and observed_candidates == observed_verifier_candidates
        and observed_candidates == observed_auditor_candidates
    )
    return _online_observation_payload(
        predictions,
        candidates=candidates,
        verifier_candidates=verifier_candidates,
        auditor_candidates=auditor_candidates,
        judgments=judgments,
        auditor_statuses=auditor_statuses,
        ambiguity=ambiguity,
        observed_candidates=observed_candidates,
        observed_verifier_candidates=observed_verifier_candidates,
        observed_auditor_candidates=observed_auditor_candidates,
        observed_judgments=observed_judgments,
        observed_auditor_statuses=observed_auditor_statuses,
        observed_ambiguity=observed_ambiguity,
        expected_annotation_labels=expected_annotation_labels,
        candidate_verifier_auditor_exact=exact,
        lane=lane,
    )


def _online_counters(
    predictions: list[dict[str, Any]],
) -> tuple[tuple[Counter[str], ...], set[str]]:
    candidates: Counter[str] = Counter()
    verifier_candidates: Counter[str] = Counter()
    auditor_candidates: Counter[str] = Counter()
    judgments: Counter[str] = Counter()
    auditor_statuses: Counter[str] = Counter()
    ambiguity: Counter[str] = Counter()
    expected_annotation_labels: set[str] = set()
    for prediction in predictions:
        metadata = _terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        candidate = str(generator.get("typed_candidate") or "missing")
        verifier_candidate = str(verifier.get("candidate_label") or "missing")
        judgment = str(verifier.get("candidate_verification_status") or "missing")
        audit = _mapping(verifier.get("candidate_verification_audit"))
        audited_candidate = str(audit.get("audited_candidate") or "missing")
        auditor_status = str(audit.get("status") or "missing")
        diagnostics = _mapping(prediction.get("qasper_annotation_diagnostics"))
        candidates[candidate] += 1
        verifier_candidates[verifier_candidate] += 1
        auditor_candidates[audited_candidate] += 1
        judgments[judgment] += 1
        auditor_statuses[auditor_status] += 1
        ambiguity_state = _ambiguity_label(diagnostics)
        ambiguity[ambiguity_state] += 1
        if ambiguity_state == "unambiguous":
            expected_annotation_labels.update(
                _annotation_labels(prediction, diagnostics)
            )
    return (
        (
            candidates,
            verifier_candidates,
            auditor_candidates,
            judgments,
            auditor_statuses,
            ambiguity,
        ),
        expected_annotation_labels,
    )


def _online_observation_payload(
    predictions: list[dict[str, Any]],
    *,
    candidates: Counter[str],
    verifier_candidates: Counter[str],
    auditor_candidates: Counter[str],
    judgments: Counter[str],
    auditor_statuses: Counter[str],
    ambiguity: Counter[str],
    observed_candidates: set[str],
    observed_verifier_candidates: set[str],
    observed_auditor_candidates: set[str],
    observed_judgments: set[str],
    observed_auditor_statuses: set[str],
    observed_ambiguity: set[str],
    expected_annotation_labels: set[str],
    candidate_verifier_auditor_exact: bool,
    lane: str,
) -> dict[str, Any]:
    observed_state_cells = _observed_state_cells(predictions)
    expected_state_cells = _expected_state_cells()
    return {
        "kind": "live_model_rows",
        "prediction_count": len(predictions),
        "generator_candidates": {
            candidate: candidates[candidate] for candidate in _CANDIDATE_LABELS
        },
        **_online_count_fields(
            candidates,
            verifier_candidates,
            auditor_candidates,
            judgments,
            auditor_statuses,
            ambiguity,
        ),
        **_online_label_fields(
            observed_candidates,
            observed_verifier_candidates,
            observed_auditor_candidates,
            observed_judgments,
            observed_auditor_statuses,
            observed_ambiguity,
            expected_annotation_labels,
            candidate_verifier_auditor_exact,
            lane,
        ),
        "observed_state_cells": [
            _state_cell_id(*cell) for cell in sorted(observed_state_cells)
        ],
        "observed_state_cell_count": len(observed_state_cells),
        "missing_state_cells": [
            _state_cell_id(*cell)
            for cell in sorted(expected_state_cells - observed_state_cells)
        ],
        "state_matrix_complete": bool(
            predictions and observed_state_cells == expected_state_cells
        ),
    }


def _expected_state_cells() -> set[tuple[str, str, bool]]:
    return {
        (judgment, auditor_status, ambiguous)
        for judgment in _JUDGMENTS
        for auditor_status in _AUDITOR_STATUSES
        for ambiguous in _AMBIGUITY_STATES
    }


def _observed_state_cells(
    predictions: list[dict[str, Any]],
) -> set[tuple[str, str, bool]]:
    observed: set[tuple[str, str, bool]] = set()
    for prediction in predictions:
        metadata = _terminal_metadata(prediction)
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        judgment = str(verifier.get("candidate_verification_status") or "")
        audit = _mapping(verifier.get("candidate_verification_audit"))
        auditor_status = str(audit.get("status") or "")
        ambiguity = _ambiguity_label(
            _mapping(prediction.get("qasper_annotation_diagnostics"))
        )
        if (
            judgment in _JUDGMENTS
            and auditor_status in _AUDITOR_STATUSES
            and ambiguity in {"ambiguous", "unambiguous"}
        ):
            observed.add((judgment, auditor_status, ambiguity == "ambiguous"))
    return observed


def _state_cell_id(judgment: str, auditor_status: str, ambiguous: bool) -> str:
    return f"{judgment}:{auditor_status}:{'ambiguous' if ambiguous else 'unambiguous'}"


def _online_label_fields(
    observed_candidates: set[str],
    observed_verifier_candidates: set[str],
    observed_auditor_candidates: set[str],
    observed_judgments: set[str],
    observed_auditor_statuses: set[str],
    observed_ambiguity: set[str],
    expected_annotation_labels: set[str],
    candidate_verifier_auditor_exact: bool,
    lane: str,
) -> dict[str, Any]:
    missing_annotation_labels = sorted(expected_annotation_labels - observed_candidates)
    if lane == _QUALITY_LANE:
        required_candidate_labels = {"yes", "no"}
        required_verifier_judgments: set[str] = set()
        required_auditor_statuses: set[str] = set()
        required_ambiguity_states: set[str] = set()
    elif lane == _CONTRACT_PROBE_LANE:
        required_candidate_labels = set(_REQUIRED_ONLINE_CANDIDATE_LABELS)
        required_verifier_judgments = set(_REQUIRED_ONLINE_VERIFIER_JUDGMENTS)
        required_auditor_statuses = set(_REQUIRED_ONLINE_AUDITOR_STATUSES)
        required_ambiguity_states = set(_REQUIRED_ONLINE_ANNOTATION_STATES)
    else:
        required_candidate_labels = set(_REQUIRED_ONLINE_CANDIDATE_LABELS)
        required_verifier_judgments = set(_REQUIRED_ONLINE_VERIFIER_JUDGMENTS)
        required_auditor_statuses = set(_REQUIRED_ONLINE_AUDITOR_STATUSES)
        required_ambiguity_states = set(_REQUIRED_ONLINE_ANNOTATION_STATES)
    missing_required_candidate_labels = sorted(
        required_candidate_labels - observed_candidates
    )
    missing_required_verifier_judgments = sorted(
        required_verifier_judgments - observed_judgments
    )
    missing_required_auditor_statuses = sorted(
        required_auditor_statuses - observed_auditor_statuses
    )
    missing_required_ambiguity_states = sorted(
        required_ambiguity_states - observed_ambiguity
    )
    return {
        "lane": lane,
        "observed_candidate_labels": sorted(observed_candidates),
        "observed_verifier_candidate_labels": sorted(observed_verifier_candidates),
        "observed_auditor_candidate_labels": sorted(observed_auditor_candidates),
        "candidate_verifier_auditor_label_sets": {
            "candidate": sorted(observed_candidates),
            "verifier": sorted(observed_verifier_candidates),
            "auditor": sorted(observed_auditor_candidates),
            "exact_match": candidate_verifier_auditor_exact,
        },
        "candidate_verifier_auditor_label_set_mismatch": not candidate_verifier_auditor_exact,
        "missing_candidate_labels_from_verifier": sorted(
            observed_candidates - observed_verifier_candidates
        ),
        "unexpected_verifier_candidate_labels": sorted(
            observed_verifier_candidates - observed_candidates
        ),
        "missing_candidate_labels_from_auditor": sorted(
            observed_candidates - observed_auditor_candidates
        ),
        "unexpected_auditor_candidate_labels": sorted(
            observed_auditor_candidates - observed_candidates
        ),
        "expected_annotation_labels": sorted(expected_annotation_labels),
        "candidate_label_diversity": len(observed_candidates),
        "expected_annotation_label_diversity": len(expected_annotation_labels),
        "missing_annotation_labels_from_candidates": missing_annotation_labels,
        "single_label_collapse": bool(
            missing_annotation_labels or missing_required_candidate_labels
        ),
        "observed_verifier_judgment_labels": sorted(observed_judgments),
        "observed_auditor_status_labels": sorted(observed_auditor_statuses),
        "observed_annotation_ambiguity_states": sorted(observed_ambiguity),
        "missing_required_candidate_labels": missing_required_candidate_labels,
        "missing_required_verifier_judgments": missing_required_verifier_judgments,
        "missing_required_auditor_statuses": missing_required_auditor_statuses,
        "missing_required_annotation_ambiguity_states": missing_required_ambiguity_states,
    }


def _online_count_fields(
    candidates: Counter[str],
    verifier_candidates: Counter[str],
    auditor_candidates: Counter[str],
    judgments: Counter[str],
    auditor_statuses: Counter[str],
    ambiguity: Counter[str],
) -> dict[str, Any]:
    return {
        "verifier_judgments": {
            judgment: judgments[judgment] for judgment in _JUDGMENTS
        },
        "auditor_statuses": {
            status: auditor_statuses[status] for status in _AUDITOR_STATUSES
        },
        "annotation_ambiguity": {
            state: ambiguity[state] for state in ("ambiguous", "unambiguous")
        },
        "unrecognized_verifier_judgment_count": sum(
            count for key, count in judgments.items() if key not in _JUDGMENTS
        ),
        "unrecognized_auditor_status_count": sum(
            count
            for key, count in auditor_statuses.items()
            if key not in _AUDITOR_STATUSES
        ),
        "unrecognized_generator_candidate_count": sum(
            count for key, count in candidates.items() if key not in _CANDIDATE_LABELS
        ),
        "unrecognized_verifier_candidate_count": sum(
            count
            for key, count in verifier_candidates.items()
            if key not in _CANDIDATE_LABELS
        ),
        "unrecognized_auditor_candidate_count": sum(
            count
            for key, count in auditor_candidates.items()
            if key not in _CANDIDATE_LABELS
        ),
    }


def _ambiguity_label(diagnostics: Mapping[str, Any]) -> str:
    if diagnostics.get("ambiguous") is True:
        return "ambiguous"
    if diagnostics.get("ambiguous") is False:
        return "unambiguous"
    return "missing"


def _recognized_labels(counter: Counter[str], labels: tuple[str, ...]) -> set[str]:
    return {label for label in labels if counter[label]}


def _observed_label_set(counter: Counter[str]) -> set[str]:
    """Keep invalid labels visible to the exact-set gate."""

    return {label for label, count in counter.items() if count and label != "missing"}


def _annotation_labels(
    prediction: Mapping[str, Any], diagnostics: Mapping[str, Any]
) -> set[str]:
    labels = _normalized_labels(diagnostics.get("canonical_answer_classes"))
    return labels or _normalized_labels(prediction.get("gold_answers"))


def _normalized_labels(value: Any) -> set[str]:
    if isinstance(value, str):
        normalized = value.strip().casefold()
        aliases = {
            "true": "yes",
            "false": "no",
            "insufficient evidence": "unanswerable",
        }
        normalized = aliases.get(normalized, normalized)
        return {normalized} if normalized in {"yes", "no", "unanswerable"} else set()
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {label for item in value for label in _normalized_labels(item)}


def _terminal_metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    bundle = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    return _mapping(bundle.get("metadata")) or _mapping(
        prediction.get("evidence_metadata")
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
