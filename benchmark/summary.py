from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean
from .verification_metrics import verification_summary


def build_benchmark_summary(
    *,
    bundle: Any,
    config: Any,
    active_routes: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    backend_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_identity_summary(bundle, config, active_routes, predictions),
        **_quality_summary(predictions),
        **_format_guardrail_summary(predictions),
        **verification_summary(predictions),
        **_timing_summary(predictions),
        **_cache_summary(predictions, config.cache_mode),
        "backend_metadata": backend_metadata,
    }


def _identity_summary(
    bundle: Any,
    config: Any,
    active_routes: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dataset_name": bundle.dataset_name,
        "manifest_path": str(bundle.manifest_path),
        "suite_name": config.suite_name,
        "engine": config.engine if len(active_routes) == 1 else "matrix",
        "route": config.route,
        "scope": config.scope,
        "num_documents": len(bundle.documents),
        "num_examples": len(bundle.examples),
        "num_routes": len(active_routes),
        "num_predictions": len(predictions),
    }


def _quality_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_em": _avg_metric(predictions, "em"),
        "avg_f1": _avg_metric(predictions, "f1"),
        "avg_anls": _avg_metric(predictions, "anls"),
        "avg_page_hit": _avg_metric(predictions, "page_hit"),
        "avg_citation_recall": _avg_metric(predictions, "citation_recall"),
        "avg_citation_precision": _avg_metric(predictions, "citation_precision"),
        "avg_element_hit": _avg_metric(predictions, "element_hit"),
        **_multimodal_hit_summary(predictions),
        "avg_span_recall": _avg_metric(predictions, "span_recall"),
        "avg_image_quote_hit": _avg_metric(predictions, "image_quote_hit"),
        "avg_cross_page_evidence_hit": _avg_metric(
            predictions, "cross_page_evidence_hit"
        ),
        "avg_multimodal_answer_support": _avg_metric(
            predictions, "multimodal_answer_support"
        ),
        "avg_hard_negative_rejection": _avg_metric(
            predictions, "hard_negative_rejection"
        ),
        "avg_formula_match": _avg_metric(predictions, "formula_match"),
        "avg_numeric_match": _avg_metric(predictions, "numeric_match"),
        "avg_abstention_rate": _avg_metric(predictions, "abstained"),
        "avg_false_abstention": _avg_metric(predictions, "false_abstention"),
    }


def _format_guardrail_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_markdown_table_renderable": _avg_metric(
            predictions, "markdown_table_renderable"
        ),
        "avg_latex_renderable": _avg_metric(predictions, "latex_renderable"),
        "avg_rewrite_skipped": _avg_metric(predictions, "rewrite_skipped"),
        "avg_guardrail_expectation_match": _avg_metric(
            predictions, "guardrail_expectation_match"
        ),
    }


def _timing_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"avg_{key}": round_metric(
            safe_mean([item["timings"][key] for item in predictions])
        )
        for key in (
            "retrieval_seconds",
            "generation_seconds",
            "parse_seconds",
            "index_seconds",
        )
    }


def _cache_summary(
    predictions: list[dict[str, Any]],
    cache_mode: str,
) -> dict[str, Any]:
    return {
        "cache_mode": cache_mode,
        "parse_cache_hits": _sum_cache_stat(predictions, "parse", "hits"),
        "parse_cache_misses": _sum_cache_stat(predictions, "parse", "misses"),
        "parse_cache_writes": _sum_cache_stat(predictions, "parse", "writes"),
        "parse_cache_hit_rate": _cache_hit_rate(predictions, "parse"),
        "embedding_cache_hits": _sum_cache_stat(predictions, "embedding", "hits"),
        "embedding_cache_misses": _sum_cache_stat(predictions, "embedding", "misses"),
        "embedding_cache_writes": _sum_cache_stat(predictions, "embedding", "writes"),
        "embedding_cache_hit_rate": _cache_hit_rate(predictions, "embedding"),
    }


def _avg_metric(predictions: list[dict[str, Any]], metric: str) -> float | None:
    return round_metric(
        safe_mean([item["metrics"].get(metric) for item in predictions])
    )


def _sum_cache_stat(predictions: list[dict[str, Any]], section: str, stat: str) -> int:
    return sum(
        int(((prediction.get("cache") or {}).get(section) or {}).get(stat, 0) or 0)
        for prediction in predictions
    )


def _cache_hit_rate(predictions: list[dict[str, Any]], section: str) -> float | None:
    hits = _sum_cache_stat(predictions, section, "hits")
    misses = _sum_cache_stat(predictions, section, "misses")
    total = hits + misses
    if total == 0:
        return None
    return round_metric(hits / total)


def _multimodal_hit_summary(
    predictions: list[dict[str, Any]]
) -> dict[str, float | None]:
    return {
        f"avg_{modality}_hit": _avg_metric(predictions, f"{modality}_hit")
        for modality in ("table", "figure", "formula", "slide")
    }
