from typing import Any

from .answer_summary import (
    answer_finalization_summary,
    avg_answer_tokens,
    avg_product_metric,
)
from .backend_health_summary import backend_health_summary
from .citation_headline_summary import citation_headline_summary
from .contract_invariant_metrics import contract_invariant_summary
from .dataset_decision_protocol import phase2_dataset_decision, phase2_failure_counts
from .effective_route_metrics import effective_route_stage_metric_table
from .headline_policy import headline_policy_predictions
from .mara_oriented_scores import (
    MARA_METRIC_KEYS,
    mara_proxy_score_metadata,
    mara_score_metadata,
)
from .metrics import round_metric, safe_mean
from .multimodal_route_summary import phase3_multimodal_summary
from .page_metric_summary import page_metric_summary
from .prompt_summary import benchmark_prompt_summary
from .route_output_agreement import route_output_agreement_rate
from .score_authority import (
    paper_grade_score_available,
    primary_score_label,
    score_authority_level,
)
from .semantic_answer import SEMANTIC_ANSWER_CONTRACT
from .semantic_summary import semantic_answer_coverage
from .stage_metrics import stage_metric_summary
from .summary_diagnostics import diagnostic_summary_fields
from .summary_rankings import route_rankings
from .summary_records import (
    adapter_metadata_summary,
    benchmark_identity_summary,
    per_example_metric_records,
)
from .timing_summary import route_timing_fields, timing_summary
from .verification_metrics import verification_summary
from .verifier_observability import (
    route_verifier_observability_fields,
    verifier_observability_summary,
)

_CITATION_GROUP_METRICS = (
    "citation_inline_recall",
    "citation_inline_precision",
    "citation_metadata_recall",
    "citation_metadata_precision",
)
_PRIMARY_SCORE_METRIC = "quality_avg_native_score"
_DEPLOYED_POLICY_SCORE_METRIC = "deployed_policy_avg_native_score"
_PRIMARY_SCORE_FALLBACK_METRIC = "avg_native_score"
_DIAGNOSTIC_SCORE_METRICS = ("avg_em", "avg_f1", "avg_anls")


def build_benchmark_summary(
    *,
    bundle: Any,
    config: Any,
    active_routes: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    backend_metadata: dict[str, dict[str, Any]],
    backend_health: dict[str, Any] | None = None,
    skipped_routes: list[dict[str, Any]] | None = None,
    adapter_metric_metadata: dict[str, dict[str, Any]] | None = None,
    external_adapter_metric_metadata: dict[str, Any] | None = None,
    external_adapter_metric_metadata_by_route: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    skipped_routes = skipped_routes or []
    return {
        **benchmark_identity_summary(
            bundle, config, active_routes, predictions, skipped_routes
        ),
        **(selection or {}),
        **_primary_score_summary(predictions),
        **_quality_summary(predictions),
        **_native_detail_metric_summary(predictions),
        **stage_metric_summary(predictions),
        "effective_route_stage_metric_table": effective_route_stage_metric_table(
            bundle.dataset_name,
            predictions,
        ),
        **benchmark_prompt_summary(predictions),
        **answer_finalization_summary(predictions),
        **_format_guardrail_summary(predictions),
        "phase2_dataset_decision": phase2_dataset_decision(bundle.dataset_name),
        "phase2_failure_counts": phase2_failure_counts(
            bundle.dataset_name,
            predictions,
        ),
        "phase3_multimodal_summary": phase3_multimodal_summary(
            bundle.dataset_name,
            predictions,
            backend_metadata=backend_metadata,
            skipped_routes=skipped_routes,
            active_routes=active_routes,
        ),
        **verification_summary(predictions),
        **contract_invariant_summary(predictions),
        "per_example_metric_records": per_example_metric_records(
            bundle.dataset_name,
            predictions,
        ),
        **verifier_observability_summary(predictions),
        **timing_summary(predictions),
        **_cache_summary(predictions, config.cache_mode),
        **_route_report_summary(
            bundle.dataset_name, predictions, skipped_routes=skipped_routes
        ),
        **_quality_route_summary(predictions),
        "mara_score_metadata": _headline_score_metadata(
            bundle.dataset_name,
            predictions,
        ),
        "mara_proxy_score_metadata": mara_proxy_score_metadata(bundle.dataset_name),
        "backend_metadata": backend_metadata,
        **backend_health_summary(backend_health),
        **adapter_metadata_summary(
            adapter_metric_metadata=adapter_metric_metadata,
            external_adapter_metric_metadata=external_adapter_metric_metadata,
            external_adapter_metric_metadata_by_route=(
                external_adapter_metric_metadata_by_route
            ),
        ),
    }


def _route_report_summary(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    skipped_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    route_metrics = _route_metric_table(dataset_name, predictions)
    return {
        "route_metric_table": route_metrics,
        **diagnostic_summary_fields(
            dataset_name,
            predictions,
            skipped_routes=skipped_routes,
        ),
        "quality_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"qa_quality"}),
        ),
        "diagnostic_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"diagnostic", "prototype"}),
        ),
        "route_rankings": route_rankings(dataset_name, route_metrics),
    }


def add_mara_summary_fields(
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    dataset_name = str(summary.get("dataset_name") or "unknown")
    return {
        **dict(summary),
        **_primary_score_summary(predictions),
        **_quality_summary(predictions),
        **_native_detail_metric_summary(predictions),
        **stage_metric_summary(predictions),
        "effective_route_stage_metric_table": effective_route_stage_metric_table(
            dataset_name,
            predictions,
        ),
        **answer_finalization_summary(predictions),
        "phase2_dataset_decision": phase2_dataset_decision(dataset_name),
        "phase2_failure_counts": phase2_failure_counts(dataset_name, predictions),
        "phase3_multimodal_summary": phase3_multimodal_summary(
            dataset_name,
            predictions,
        ),
        **contract_invariant_summary(predictions),
        "per_example_metric_records": per_example_metric_records(
            dataset_name,
            predictions,
        ),
        **verifier_observability_summary(predictions),
        **timing_summary(predictions),
        "route_metric_table": _route_metric_table(dataset_name, predictions),
        **diagnostic_summary_fields(dataset_name, predictions),
        "quality_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"qa_quality"}),
        ),
        "diagnostic_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"diagnostic", "prototype"}),
        ),
        **_quality_route_summary(predictions),
        "route_rankings": route_rankings(
            dataset_name,
            _route_metric_table(dataset_name, predictions),
        ),
        "mara_score_metadata": _headline_score_metadata(dataset_name, predictions),
        "mara_proxy_score_metadata": mara_proxy_score_metadata(dataset_name),
    }


def _quality_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answer_quality_contract": SEMANTIC_ANSWER_CONTRACT,
        "token_f1_contract": "token_f1_v2",
        "avg_em": _avg_metric(predictions, "em"),
        "avg_f1": _avg_metric(predictions, "f1"),
        "avg_token_f1_v2": _avg_metric(predictions, "token_f1_v2"),
        "avg_legacy_token_f1": _avg_metric(predictions, "legacy_token_f1"),
        "avg_semantic_answer_precision": _avg_metric(
            predictions, "semantic_answer_precision"
        ),
        "avg_semantic_answer_recall": _avg_metric(
            predictions, "semantic_answer_recall"
        ),
        "avg_semantic_answer_f1": _avg_metric(predictions, "semantic_answer_f1"),
        **semantic_answer_coverage(predictions),
        "product_avg_em": avg_product_metric(predictions, "em"),
        "product_avg_f1": avg_product_metric(predictions, "f1"),
        "avg_anls": _avg_metric(predictions, "anls"),
        "avg_page_hit": _avg_metric(predictions, "page_hit"),
        "avg_strict_page_hit": _avg_metric(predictions, "strict_page_hit"),
        "avg_equivalent_evidence_page_hit": _avg_metric(
            predictions,
            "equivalent_evidence_page_hit",
        ),
        **page_metric_summary(predictions),
        "route_output_agreement_rate": route_output_agreement_rate(predictions),
        **citation_headline_summary(predictions),
        **_citation_group_summary(predictions),
        **_citation_locator_summary(predictions),
        "avg_element_hit": _avg_metric(predictions, "element_hit"),
        "avg_element_locator_hit": _avg_metric(predictions, "element_locator_hit"),
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
        **_mara_metric_summary(predictions),
    }


def _primary_score_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    quality_predictions = _role_predictions(predictions, {"qa_quality"})
    primary_predictions, policy = headline_policy_predictions(quality_predictions)
    if primary_predictions:
        paper_grade = paper_grade_score_available(primary_predictions)
        return {
            "primary_score_metric": (
                _DEPLOYED_POLICY_SCORE_METRIC
                if policy
                in {
                    "deployed_controller_policy",
                    "deployed_manifest_policy",
                }
                else _PRIMARY_SCORE_METRIC
            ),
            "primary_score": _avg_metric(primary_predictions, "native_score"),
            "primary_score_label": primary_score_label(paper_grade),
            "primary_score_scope": "qa_quality",
            "primary_score_policy": policy,
            "primary_score_routes": _ordered_routes(primary_predictions),
            "score_authority_level": score_authority_level(paper_grade),
            "paper_grade_score_available": paper_grade,
            "diagnostic_score_metrics": list(_DIAGNOSTIC_SCORE_METRICS),
        }
    paper_grade = paper_grade_score_available(predictions)
    return {
        "primary_score_metric": _PRIMARY_SCORE_FALLBACK_METRIC,
        "primary_score": _avg_metric(predictions, "native_score"),
        "primary_score_label": primary_score_label(paper_grade),
        "primary_score_scope": "all_routes_fallback",
        "primary_score_policy": "all_routes_fallback",
        "primary_score_routes": _ordered_routes(predictions),
        "score_authority_level": score_authority_level(paper_grade),
        "paper_grade_score_available": paper_grade,
        "diagnostic_score_metrics": list(_DIAGNOSTIC_SCORE_METRICS),
    }


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _quality_route_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    quality_predictions = _role_predictions(predictions, {"qa_quality"})
    return {
        "quality_avg_em": _avg_metric(quality_predictions, "em"),
        "quality_avg_f1": _avg_metric(quality_predictions, "f1"),
        "quality_avg_semantic_answer_f1": _avg_metric(
            quality_predictions, "semantic_answer_f1"
        ),
        "quality_product_avg_em": avg_product_metric(quality_predictions, "em"),
        "quality_product_avg_f1": avg_product_metric(quality_predictions, "f1"),
        "quality_avg_mara_score": _avg_metric(quality_predictions, "mara_score"),
        "quality_avg_native_score": _avg_metric(quality_predictions, "native_score"),
        "quality_avg_mara_proxy_score": _avg_metric(
            quality_predictions,
            "mara_proxy_score",
        ),
        "quality_avg_numeric_match": _avg_metric(quality_predictions, "numeric_match"),
        "quality_avg_citation_inline_recall": _avg_metric(
            quality_predictions,
            "citation_inline_recall",
        ),
        "quality_avg_citation_metadata_recall": _avg_metric(
            quality_predictions,
            "citation_metadata_recall",
        ),
    }


def _mara_metric_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"avg_{metric}": _avg_metric(predictions, metric) for metric in MARA_METRIC_KEYS
    }


def _native_detail_metric_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_{metric}": _avg_metric(predictions, metric)
        for metric in _native_detail_metric_keys(predictions)
    }


def _native_detail_metric_keys(predictions: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for prediction in predictions:
        metrics = dict(prediction.get("metrics") or {})
        for metric in prediction.get("mara_native_metrics") or ():
            metric_name = str(metric).strip()
            if metric_name and metric_name in metrics and metric_name not in keys:
                keys.append(metric_name)
    return keys


def _headline_score_metadata(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    external_predictions = [
        prediction
        for prediction in predictions
        if prediction.get("mara_scoring_source") == "external_paper_grade"
    ]
    if not external_predictions:
        return _local_headline_score_metadata(dataset_name, predictions)
    return {
        "scoring_mode": "paper_grade_external_v1",
        "paper_grade": True,
        "contracts": _count_values(
            [
                str(prediction.get("mara_scoring_contract") or "").strip()
                for prediction in external_predictions
                if str(prediction.get("mara_scoring_contract") or "").strip()
            ]
        ),
        "primary_metrics": _count_values(
            [
                str(prediction.get("mara_primary_metric") or "").strip()
                for prediction in external_predictions
                if str(prediction.get("mara_primary_metric") or "").strip()
            ]
        ),
        "local_fallback_metadata": mara_score_metadata(dataset_name),
    }


def _local_headline_score_metadata(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    fallback = mara_score_metadata(dataset_name)
    contracts = _count_values(
        [
            str(prediction.get("mara_scoring_contract") or "").strip()
            for prediction in predictions
            if str(prediction.get("mara_scoring_contract") or "").strip()
        ]
    )
    primary_metrics = _count_values(
        [
            str(prediction.get("mara_primary_metric") or "").strip()
            for prediction in predictions
            if str(prediction.get("mara_primary_metric") or "").strip()
        ]
    )
    if not contracts:
        return fallback
    if contracts == {fallback["contract_id"]: len(predictions)}:
        return fallback
    return {
        "scoring_mode": "dataset_native_v1",
        "paper_grade": False,
        "contracts": contracts,
        "primary_metrics": primary_metrics,
        "local_fallback_metadata": fallback,
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
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_{modality}_hit": _avg_metric(predictions, f"{modality}_hit")
        for modality in ("table", "figure", "formula", "slide")
    }


def _citation_locator_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_citation_{metric}_{locator}": _avg_metric(
            predictions, f"citation_{metric}_{locator}"
        )
        for metric in ("recall", "precision")
        for locator in ("source", "page", "span")
    }


def _citation_group_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_{metric}": _avg_metric(predictions, metric)
        for metric in _CITATION_GROUP_METRICS
    }


def _route_metric_table(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in _ordered_routes(predictions):
        route_predictions = [
            prediction
            for prediction in predictions
            if str(prediction.get("route") or "") == route
        ]
        rows.append(
            {
                "dataset_name": dataset_name,
                "route": route,
                "num_predictions": len(route_predictions),
                "avg_em": _avg_metric(route_predictions, "em"),
                "avg_f1": _avg_metric(route_predictions, "f1"),
                "avg_semantic_answer_f1": _avg_metric(
                    route_predictions, "semantic_answer_f1"
                ),
                "product_avg_em": avg_product_metric(route_predictions, "em"),
                "product_avg_f1": avg_product_metric(route_predictions, "f1"),
                "avg_answer_for_user_tokens": avg_answer_tokens(
                    route_predictions,
                    "answer_for_user",
                ),
                "avg_answer_for_scoring_tokens": avg_answer_tokens(
                    route_predictions,
                    "answer_for_scoring",
                ),
                **_mara_metric_summary(route_predictions),
                **_native_detail_metric_summary(route_predictions),
                "avg_anls": _avg_metric(route_predictions, "anls"),
                "avg_page_hit": _avg_metric(route_predictions, "page_hit"),
                "avg_strict_page_hit": _avg_metric(
                    route_predictions,
                    "strict_page_hit",
                ),
                "avg_equivalent_evidence_page_hit": _avg_metric(
                    route_predictions,
                    "equivalent_evidence_page_hit",
                ),
                **page_metric_summary(route_predictions),
                "avg_element_hit": _avg_metric(route_predictions, "element_hit"),
                "avg_element_locator_hit": _avg_metric(
                    route_predictions, "element_locator_hit"
                ),
                "avg_citation_recall": _avg_metric(
                    route_predictions, "citation_recall"
                ),
                "avg_citation_precision": _avg_metric(
                    route_predictions, "citation_precision"
                ),
                **_citation_group_summary(route_predictions),
                **_citation_locator_summary(route_predictions),
                "avg_unsupported_claim_rate": _avg_metric(
                    route_predictions, "unsupported_claim_rate"
                ),
                "avg_abstention_rate": _avg_metric(route_predictions, "abstained"),
                **route_verifier_observability_fields(route_predictions),
                "avg_multimodal_answer_support": _avg_metric(
                    route_predictions, "multimodal_answer_support"
                ),
                **route_timing_fields(route_predictions),
                **stage_metric_summary(route_predictions),
                "benchmark_role": _route_role(route_predictions),
            }
        )
    return rows


def _ordered_routes(predictions: list[dict[str, Any]]) -> list[str]:
    routes: list[str] = []
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        if route and route not in routes:
            routes.append(route)
    return routes


def _role_predictions(
    predictions: list[dict[str, Any]],
    roles: set[str],
) -> list[dict[str, Any]]:
    return [
        prediction
        for prediction in predictions
        if str(prediction.get("benchmark_role") or "qa_quality") in roles
    ]


def _route_role(predictions: list[dict[str, Any]]) -> str:
    for prediction in predictions:
        role = str(prediction.get("benchmark_role") or "").strip()
        if role:
            return role
    return "qa_quality"
