from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

STATE_MATRIX_CONTRACT = "qasper_candidate_bound_state_matrix.v1"
_JUDGMENTS = ("supported", "contradicted", "unknown")
_AUDITOR_STATUSES = ("passed", "failed")
_AMBIGUITY_STATES = (False, True)


def qasper_candidate_bound_state_matrix(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project the immutable-candidate contract separately from live coverage."""

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
        "online_observation": _online_observation(predictions),
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


def _online_observation(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: Counter[str] = Counter()
    judgments: Counter[str] = Counter()
    auditor_statuses: Counter[str] = Counter()
    ambiguity: Counter[str] = Counter()
    expected_annotation_labels: set[str] = set()
    for prediction in predictions:
        metadata = _terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        candidate = str(generator.get("typed_candidate") or "missing")
        judgment = str(verifier.get("candidate_verification_status") or "missing")
        audit = _mapping(verifier.get("candidate_verification_audit"))
        auditor_status = str(audit.get("status") or "missing")
        diagnostics = _mapping(prediction.get("qasper_annotation_diagnostics"))
        candidates[candidate] += 1
        judgments[judgment] += 1
        auditor_statuses[auditor_status] += 1
        ambiguity[
            "ambiguous" if diagnostics.get("ambiguous") is True else "unambiguous"
        ] += 1
        if diagnostics.get("ambiguous") is not True:
            expected_annotation_labels.update(
                _annotation_labels(prediction, diagnostics)
            )
    candidate_labels = ("yes", "no", "unanswerable")
    candidate_diversity = sum(bool(candidates[label]) for label in candidate_labels)
    return {
        "kind": "live_model_rows",
        "prediction_count": len(predictions),
        "generator_candidates": {
            candidate: candidates[candidate] for candidate in candidate_labels
        },
        "expected_annotation_labels": sorted(expected_annotation_labels),
        "candidate_label_diversity": candidate_diversity,
        "expected_annotation_label_diversity": len(expected_annotation_labels),
        "single_label_collapse": bool(
            len(expected_annotation_labels) >= 2 and candidate_diversity < 2
        ),
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
            count for key, count in candidates.items() if key not in candidate_labels
        ),
    }


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
