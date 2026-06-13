from __future__ import annotations

from typing import Any

from .metrics import (
    anls_score,
    citation_precision_score,
    citation_recall_score,
    cross_page_evidence_hit_score,
    element_hit_score,
    exact_match_score,
    false_abstention_score,
    formula_normalized_match_score,
    hard_negative_rejection_score,
    image_quote_hit_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    modality_hit_score,
    multimodal_support_score,
    numeric_tolerance_score,
    page_hit_score,
    recall_score,
    span_recall_score,
    token_f1_score,
)
from .verification_metrics import verification_metrics

_TABLE_FORMATS = {"markdown_table", "markdown-table", "table"}
_LATEX_FORMATS = {"latex", "math", "formula", "math_formula", "math-formula"}
_TIMING_KEYS = (
    "parse_seconds",
    "index_seconds",
    "retrieval_seconds",
    "generation_seconds",
)
_CACHE_KEYS = ("hits", "misses", "writes")


def score_prediction(prediction: dict[str, Any]) -> dict[str, float | None]:
    gold_answers = prediction["gold_answers"]
    predicted_answer = prediction["predicted_answer"]
    expected_formats = _normalized_expected_formats(prediction)
    claim_verification = dict(prediction.get("claim_verification") or {})
    abstained = _prediction_abstained(prediction, predicted_answer, claim_verification)
    markdown_table_score = markdown_table_renderable_score(predicted_answer)
    latex_score = latex_renderable_score(predicted_answer)
    if expected_formats & _TABLE_FORMATS and markdown_table_score is None:
        markdown_table_score = 0.0
    if expected_formats & _LATEX_FORMATS and latex_score is None:
        latex_score = 0.0
    false_abstention = false_abstention_score(predicted_answer, gold_answers)
    if abstained and any(str(answer or "").strip() for answer in gold_answers):
        false_abstention = 1.0

    metrics = {
        "em": exact_match_score(predicted_answer, gold_answers),
        "f1": token_f1_score(predicted_answer, gold_answers),
        "anls": anls_score(predicted_answer, gold_answers),
        "formula_match": formula_normalized_match_score(predicted_answer, gold_answers),
        "numeric_match": numeric_tolerance_score(predicted_answer, gold_answers),
        "page_hit": page_hit_score(
            prediction["predicted_pages"], prediction["gold_pages"]
        ),
        "citation_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
        "abstained": float(abstained),
        "false_abstention": false_abstention,
        "markdown_table_renderable": markdown_table_score,
        "latex_renderable": latex_score,
        "rewrite_skipped": float(bool(claim_verification.get("rewrite_skipped"))),
        "guardrail_expectation_match": _guardrail_expectation_match(
            prediction, abstained
        ),
    }
    for modality in ("table", "figure", "formula", "slide"):
        metrics[f"{modality}_hit"] = modality_hit_score(
            modality,
            expected_modality=str(prediction.get("modality") or ""),
            evidence_metadata=dict(prediction.get("evidence_metadata") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=list(prediction.get("gold_evidence") or []),
        )
    metrics.update(verification_metrics(prediction))
    gold_evidence = prediction.get("gold_evidence", [])
    if gold_evidence:
        metrics["element_hit"] = element_hit_score(
            prediction.get("predicted_element_ids", []), gold_evidence
        )
        metrics["span_recall"] = span_recall_score(predicted_answer, gold_evidence)
        metrics["image_quote_hit"] = image_quote_hit_score(
            predicted_answer, gold_evidence
        )
        metrics["multimodal_answer_support"] = multimodal_support_score(
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
        )
        metrics["hard_negative_rejection"] = hard_negative_rejection_score(
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
        )
        metrics["citation_recall"] = citation_recall_score(
            prediction["predicted_sources"], gold_evidence
        )
        metrics["citation_precision"] = citation_precision_score(
            prediction["predicted_sources"], gold_evidence
        )
        metrics["cross_page_evidence_hit"] = cross_page_evidence_hit_score(
            prediction["predicted_pages"],
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
        )
    return metrics


def normalize_operational_fields(prediction: dict[str, Any]) -> None:
    timings = _normalize_timings(prediction.get("timings"))
    prediction["timings"] = timings

    performance = dict(prediction.get("performance") or {})
    for key, value in _performance_from_timings(timings).items():
        performance.setdefault(key, value)
    prediction["performance"] = performance
    prediction["cache"] = _normalize_cache(prediction.get("cache"))
    prediction["cost"] = dict(prediction.get("cost") or {})


def _normalized_expected_formats(prediction: dict[str, Any]) -> set[str]:
    return {
        str(item).strip().lower()
        for item in prediction.get("expected_formats", [])
        if str(item).strip()
    }


def _guardrail_abstained(prediction: dict[str, Any]) -> bool:
    guardrail = dict(prediction.get("guardrail_decision") or {})
    action = str(guardrail.get("action") or "").strip().lower()
    status = str(guardrail.get("status") or "").strip().lower()
    return action == "abstain" or status in {"not_enough_evidence", "unsupported"}


def _prediction_abstained(
    prediction: dict[str, Any],
    predicted_answer: str,
    claim_verification: dict[str, Any],
) -> bool:
    return (
        bool(claim_verification.get("abstained"))
        or _guardrail_abstained(prediction)
        or is_abstention_answer(predicted_answer)
    )


def _guardrail_expectation_match(
    prediction: dict[str, Any],
    abstained: bool,
) -> float | None:
    expected = dict(prediction.get("expected_guardrails") or {})
    if not expected:
        return None

    claim_verification = dict(prediction.get("claim_verification") or {})
    checks: list[bool] = []
    if "rewrite_skipped" in expected:
        checks.append(
            bool(claim_verification.get("rewrite_skipped"))
            == bool(expected["rewrite_skipped"])
        )
    if "allow_abstention" in expected:
        checks.append(bool(expected["allow_abstention"]) or not abstained)
    if not checks:
        return None
    return sum(1 for item in checks if item) / len(checks)


def _normalize_timings(timings: dict[str, Any] | None) -> dict[str, float]:
    source = timings or {}
    return {key: round(float(source.get(key, 0.0) or 0.0), 4) for key in _TIMING_KEYS}


def _normalize_cache_stats(stats: dict[str, Any] | None) -> dict[str, int]:
    source = stats or {}
    return {key: int(source.get(key, 0) or 0) for key in _CACHE_KEYS}


def _normalize_cache(cache: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    source = cache or {}
    return {
        "parse": _normalize_cache_stats(source.get("parse")),
        "embedding": _normalize_cache_stats(source.get("embedding")),
    }


def _performance_from_timings(timings: dict[str, float]) -> dict[str, Any]:
    return {
        **timings,
        "total_seconds": round(sum(timings.values()), 4),
    }
