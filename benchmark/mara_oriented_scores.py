from __future__ import annotations

from typing import Any

from .dataset_profiles import profile_for_dataset
from .metrics import round_metric, safe_mean

MARA_COMPONENT_KEYS = (
    "mara_answer_score",
    "mara_evidence_score",
    "mara_citation_score",
    "mara_groundedness_score",
    "mara_abstention_score",
    "mara_controller_score",
    "mara_format_score",
)
MARA_METRIC_KEYS = ("mara_score", *MARA_COMPONENT_KEYS)

_ANSWER_KEYS = ("em", "numeric_match", "formula_match", "anls", "f1")
_EVIDENCE_KEYS = (
    "page_hit",
    "span_recall",
    "element_hit",
    "cross_page_evidence_hit",
    "multimodal_answer_support",
)
_DIAGNOSTIC_EVIDENCE_KEYS = (
    "gold_document_hit",
    "gold_page_hit",
    "gold_span_hit",
)
_CITATION_KEYS = (
    "citation_recall",
    "citation_precision",
    "citation_recall_source",
    "citation_precision_source",
    "citation_recall_page",
    "citation_precision_page",
    "citation_recall_span",
    "citation_precision_span",
)
_FORMAT_REQUIREMENTS = {
    "markdown_table": "markdown_table_renderable",
    "markdown-table": "markdown_table_renderable",
    "table": "markdown_table_renderable",
    "latex": "latex_renderable",
    "math": "latex_renderable",
    "formula": "latex_renderable",
    "math_formula": "latex_renderable",
    "math-formula": "latex_renderable",
}
_PROFILE_WEIGHTS = {
    "structured_qa": {
        "mara_answer_score": 0.30,
        "mara_evidence_score": 0.25,
        "mara_citation_score": 0.20,
        "mara_groundedness_score": 0.15,
        "mara_abstention_score": 0.05,
        "mara_controller_score": 0.05,
        "mara_format_score": 0.05,
    },
    "citation_qa": {
        "mara_answer_score": 0.15,
        "mara_evidence_score": 0.25,
        "mara_citation_score": 0.30,
        "mara_groundedness_score": 0.15,
        "mara_abstention_score": 0.05,
        "mara_controller_score": 0.05,
        "mara_format_score": 0.05,
    },
    "groundedness": {
        "mara_answer_score": 0.0,
        "mara_evidence_score": 0.20,
        "mara_citation_score": 0.10,
        "mara_groundedness_score": 0.40,
        "mara_abstention_score": 0.20,
        "mara_controller_score": 0.05,
        "mara_format_score": 0.05,
    },
    "visual_qa": {
        "mara_answer_score": 0.20,
        "mara_evidence_score": 0.35,
        "mara_citation_score": 0.15,
        "mara_groundedness_score": 0.10,
        "mara_abstention_score": 0.05,
        "mara_controller_score": 0.10,
        "mara_format_score": 0.05,
    },
}


def mara_oriented_metrics(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> dict[str, float | None]:
    profile = mara_profile_for_prediction(prediction, dataset_name=dataset_name)
    weights = _PROFILE_WEIGHTS[profile]
    components = {
        "mara_answer_score": _answer_score(prediction, profile),
        "mara_evidence_score": _evidence_score(prediction),
        "mara_citation_score": _citation_score(prediction),
        "mara_groundedness_score": _groundedness_score(prediction),
        "mara_abstention_score": _abstention_score(prediction),
        "mara_controller_score": _controller_score(prediction),
        "mara_format_score": _format_score(prediction),
    }
    return {"mara_score": _weighted_score(components, weights), **components}


def add_mara_oriented_metrics(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> None:
    prediction["metrics"] = {
        **dict(prediction.get("metrics") or {}),
        **mara_oriented_metrics(prediction, dataset_name=dataset_name),
    }
    prediction["mara_score_profile"] = mara_profile_for_prediction(
        prediction,
        dataset_name=dataset_name,
    )


def mara_profile_for_prediction(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> str:
    profile = profile_for_dataset(dataset_name)
    family = profile.dataset_family
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    modality = str(prediction.get("modality") or "").strip().lower()
    if family == "ragtruth" or answer_type == "verification":
        return "groundedness"
    if profile.capabilities.multimodal or modality not in {"", "text"}:
        return "visual_qa"
    if profile.capabilities.source_level_citations:
        return "citation_qa"
    return "structured_qa"


def mara_score_metadata(dataset_name: str) -> dict[str, Any]:
    profile_name = mara_profile_for_prediction({}, dataset_name=dataset_name)
    return {
        "scoring_mode": "deterministic_v1",
        "default_profile": profile_name,
        "profile_weights": _PROFILE_WEIGHTS[profile_name],
    }


def _answer_score(prediction: dict[str, Any], profile: str) -> float | None:
    if profile == "groundedness":
        return None
    values = [_metric(prediction, key) for key in _ANSWER_KEYS]
    scores = [value for value in values if value is not None]
    if not scores:
        return None
    return round_metric(max(scores))


def _evidence_score(prediction: dict[str, Any]) -> float | None:
    metrics = [_metric(prediction, key) for key in _EVIDENCE_KEYS]
    diagnostics = [_diagnostic(prediction, key) for key in _DIAGNOSTIC_EVIDENCE_KEYS]
    return _mean_score([*metrics, *diagnostics])


def _citation_score(prediction: dict[str, Any]) -> float | None:
    return _mean_score([_metric(prediction, key) for key in _CITATION_KEYS])


def _groundedness_score(prediction: dict[str, Any]) -> float | None:
    unsupported = _metric(prediction, "unsupported_claim_rate")
    contradictions = _metric(prediction, "contradiction_count")
    scores: list[float | None] = []
    if unsupported is not None:
        scores.append(1.0 - min(max(unsupported, 0.0), 1.0))
    if contradictions is not None:
        scores.append(1.0 - min(max(contradictions, 0.0), 1.0))
    return _mean_score(scores)


def _abstention_score(prediction: dict[str, Any]) -> float | None:
    direct_scores = [
        _metric(prediction, "abstention_correctness"),
        _metric(prediction, "guardrail_expectation_match"),
    ]
    direct = _mean_score(direct_scores)
    if direct is not None:
        return direct
    false_abstention = _metric(prediction, "false_abstention")
    if false_abstention is None:
        return None
    return round_metric(1.0 - min(max(false_abstention, 0.0), 1.0))


def _controller_score(prediction: dict[str, Any]) -> float | None:
    return _diagnostic(prediction, "controller_route_match")


def _format_score(prediction: dict[str, Any]) -> float | None:
    expected_formats = {
        str(item).strip().lower()
        for item in prediction.get("expected_formats", [])
        if str(item).strip()
    }
    required_metrics = {
        metric
        for expected_format, metric in _FORMAT_REQUIREMENTS.items()
        if expected_format in expected_formats
    }
    if not required_metrics:
        return None
    return _mean_score([_metric(prediction, key) for key in sorted(required_metrics)])


def _weighted_score(
    components: dict[str, float | None],
    weights: dict[str, float],
) -> float | None:
    weighted_values = [
        (value, weights[key])
        for key, value in components.items()
        if value is not None and weights.get(key, 0.0) > 0.0
    ]
    denominator = sum(weight for _, weight in weighted_values)
    if denominator == 0.0:
        return None
    numerator = sum(value * weight for value, weight in weighted_values)
    return round_metric(numerator / denominator)


def _mean_score(values: list[float | None]) -> float | None:
    return round_metric(safe_mean([value for value in values if value is not None]))


def _metric(prediction: dict[str, Any], key: str) -> float | None:
    return _coerce_score((prediction.get("metrics") or {}).get(key))


def _diagnostic(prediction: dict[str, Any], key: str) -> float | None:
    return _coerce_score((prediction.get("diagnostics") or {}).get(key))


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
