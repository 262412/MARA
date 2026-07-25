from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .baseline_registry import assert_writable_benchmark_output
from .dataset_decision_report import (
    phase2_failure_counts_markdown,
    phase2_summary_markdown,
)
from .multimodal_route_report import phase3_report_sections, phase3_summary_markdown
from .report_benchmark_taxonomy import (
    failure_taxonomy_by_route_markdown,
    failure_taxonomy_markdown,
    routing_taxonomy_markdown,
)
from .report_compaction_fields import TEXT_FIELDS
from .report_external_evaluators import (
    external_evaluator_by_route_markdown,
    external_evaluator_markdown,
)
from .report_headline import headline_score_lines
from .report_identity_compaction import (
    IDENTITY_TRACE_LIMITS,
    compact_identity_evidence_list,
)
from .report_route_metrics import route_metrics_markdown
from .report_route_rankings import route_ranking_markdown
from .report_summary_metrics import diagnostic_metric_lines
from .report_verifier_observability import verifier_observability_markdown

ARTIFACT_LIMITS = {
    "max_evidence_text_chars": 2000,
    "max_prediction_evidence_items": 10,
    "max_trace_events": 20,
    **IDENTITY_TRACE_LIMITS,
}
_TRACE_FIELDS = {
    "agent_trace",
    "controller_trace",
    "retrieval_trace",
    "trace",
    "events",
}
_EVIDENCE_LIST_FIELDS = {
    "candidate_evidence",
    "element_index",
    "evidence",
    "graph_evidence",
    "items",
    "page_image_index",
    "reranked_evidence",
    "retrieved_hits",
}
_SCORE_MAP_FIELDS = {
    "element_retriever_scores",
    "item_scores",
    "visual_retriever_scores",
}
_REFERENCE_LIST_FIELDS = {
    "source_backrefs",
}
_COMPACT_DROP_FIELDS = {
    "image_origin",
    "image_ref",
    "late_interaction_tokens",
    "multi_vector_representation",
    "page_image_path",
    "page_visual_embedding",
    "rendered_page_image",
    "visual_embedding",
}
_CSV_FIELD_ORDER = [
    "dataset_name",
    "route",
    "num_predictions",
    "avg_mara_score",
    "avg_native_score",
    "avg_mara_proxy_score",
    "avg_em",
    "avg_f1",
    "avg_semantic_answer_f1",
    "product_avg_em",
    "product_avg_f1",
    "avg_answer_for_user_tokens",
    "avg_answer_for_scoring_tokens",
    "avg_mara_answer_score",
    "avg_mara_evidence_score",
    "avg_mara_citation_score",
    "avg_mara_groundedness_score",
    "avg_mara_abstention_score",
    "avg_mara_controller_score",
    "avg_mara_format_score",
    "avg_anls",
    "avg_page_hit",
    "avg_citation_recall",
    "avg_citation_precision",
    "avg_citation_metadata_recall",
    "avg_citation_metadata_precision",
    "avg_citation_inline_recall",
    "avg_citation_inline_precision",
    "avg_citation_recall_source",
    "avg_citation_precision_source",
    "avg_citation_recall_page",
    "avg_citation_precision_page",
    "avg_citation_recall_span",
    "avg_citation_precision_span",
    "avg_unsupported_claim_rate",
    "avg_abstention_rate",
    "num_true_abstention",
    "num_false_abstention",
    "num_unsupported_claim",
    "total_unsupported_claim_count",
    "num_retry",
    "total_retry_count",
    "num_route_switch",
    "total_route_switch_count",
    "avg_multimodal_answer_support",
    "avg_total_seconds",
    "median_total_seconds",
    "p95_total_seconds",
    "avg_total_seconds_including_preparation",
    "median_total_seconds_including_preparation",
    "p95_total_seconds_including_preparation",
    "num_route_timeouts",
    "benchmark_role",
]


def _to_slug(text: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "benchmark"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _derive_retrieval_traces(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for prediction in predictions:
        trace: dict[str, Any] = {}
        if "example_id" in prediction:
            trace["example_id"] = prediction["example_id"]
        if "retrieved_hits" in prediction:
            trace["retrieved_hits"] = prediction["retrieved_hits"]
        if "retrieval_trace" in prediction:
            trace["retrieval_trace"] = prediction["retrieval_trace"]
        for key in (
            "gold_pages",
            "gold_sources",
            "gold_evidence",
            "predicted_pages",
            "predicted_sources",
            "predicted_citations",
            "scored_predicted_sources",
        ):
            if key in prediction:
                trace[key] = prediction[key]
        for key in (
            "agent_trace",
            "evidence_metadata",
            "claim_verification",
            "verifier_observability",
            "presentation",
        ):
            if key in prediction:
                trace[key] = prediction[key]
        if "timings" in prediction:
            trace["timings"] = prediction["timings"]
        if "performance" in prediction:
            trace["performance"] = prediction["performance"]
        if "cache" in prediction:
            trace["cache"] = prediction["cache"]
        if "cost" in prediction:
            trace["cost"] = prediction["cost"]
        traces.append(trace)
    return traces


def _first_present(*sources: dict[str, Any], key: str) -> Any:
    for source in sources:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _summary_markdown_lines(summary: dict[str, Any], suite_name: str) -> list[str]:
    lines = [
        f"# {summary.get('suite_name', suite_name)}",
        "",
        f"- Dataset: `{summary.get('dataset_name')}`",
        f"- Examples: `{summary.get('num_examples')}`",
        f"- Documents: `{summary.get('num_documents')}`",
    ]
    lines.extend(headline_score_lines(summary))
    lines.extend(
        [
            f"- Diagnostic EM: `{summary.get('avg_em')}`",
            f"- Diagnostic F1: `{summary.get('avg_f1')}`",
            f"- Semantic Answer F1: `{summary.get('avg_semantic_answer_f1')}`",
            f"- Semantic Judge Coverage: `{summary.get('semantic_judge_coverage')}`",
            f"- Product Diagnostic EM: `{summary.get('product_avg_em')}`",
            f"- Product Diagnostic F1: `{summary.get('product_avg_f1')}`",
            "- Avg Answer Tokens User/Scoring: "
            f"`{summary.get('avg_answer_for_user_tokens')}` / "
            f"`{summary.get('avg_answer_for_scoring_tokens')}`",
        ]
    )
    if "quality_avg_f1" in summary:
        if "quality_avg_native_score" in summary:
            lines.append(
                "- Quality Dataset-Native Local Score: "
                f"`{summary.get('quality_avg_native_score')}`"
            )
        if "quality_avg_mara_proxy_score" in summary:
            lines.append(
                "- Quality MARA Diagnostic Proxy Score: "
                f"`{summary.get('quality_avg_mara_proxy_score')}`"
            )
        lines.append(f"- Quality Diagnostic EM: `{summary.get('quality_avg_em')}`")
        lines.append(f"- Quality Diagnostic F1: `{summary.get('quality_avg_f1')}`")
        lines.append(
            f"- Quality Numeric Match: `{summary.get('quality_avg_numeric_match')}`"
        )
    lines.extend(phase2_summary_markdown(summary))
    lines.extend(phase3_summary_markdown(summary))
    lines.extend(diagnostic_metric_lines(summary))
    return lines


def write_reports(
    report: dict[str, Any],
    output_dir: str | Path,
    suite_name: str,
    *,
    artifact_detail: str = "compact",
) -> Path:
    artifact_detail = _normalize_artifact_detail(artifact_detail)
    output_dir = Path(output_dir).resolve()
    assert_writable_benchmark_output(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{timestamp}_{_to_slug(suite_name)}"
    if run_dir.exists():
        raise FileExistsError(f"Benchmark report directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    summary_path = run_dir / "summary.json"
    predictions_path = run_dir / "predictions.jsonl"
    documents_path = run_dir / "documents.json"
    retrieval_traces_path = run_dir / "retrieval_traces.jsonl"
    markdown_path = run_dir / "report.md"
    route_metrics_path = run_dir / "route_metrics.csv"

    summary = {
        **dict(report.get("summary", {}) or {}),
        "artifact_detail": artifact_detail,
        "artifact_limits": dict(ARTIFACT_LIMITS),
    }
    config = report.get("config", {})
    predictions = _artifact_rows(report.get("predictions", []), artifact_detail)
    documents = _artifact_rows(report.get("documents", []), artifact_detail)
    retrieval_traces = report.get("retrieval_traces")
    if retrieval_traces is None:
        retrieval_traces = _derive_retrieval_traces(predictions)
    else:
        retrieval_traces = _artifact_rows(retrieval_traces, artifact_detail)

    _write_jsonl(predictions_path, predictions)
    documents_path.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_jsonl(retrieval_traces_path, retrieval_traces)
    route_metric_table = _route_metric_table(summary)
    if route_metric_table:
        _write_csv(route_metrics_path, route_metric_table)

    markdown = _summary_markdown_lines(summary, suite_name)
    for label, key in (("Engine", "engine"), ("Route", "route"), ("Scope", "scope")):
        value = _first_present(summary, config, key=key)
        if value is not None:
            markdown.append(f"- {label}: `{value}`")
    markdown += [
        "",
        "## Files",
        "",
        "- Summary: `summary.json`",
        "- Predictions: `predictions.jsonl`",
        "- Documents: `documents.json`",
        "- Retrieval Traces: `retrieval_traces.jsonl`",
    ]
    if route_metric_table:
        markdown.append("- Route Metrics: `route_metrics.csv`")
    markdown += _report_markdown_sections(summary, route_metric_table)
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def _normalize_artifact_detail(artifact_detail: str) -> str:
    value = str(artifact_detail or "compact").strip().lower()
    if value not in {"compact", "full"}:
        raise ValueError("artifact_detail must be one of 'compact' or 'full'.")
    return value


def _artifact_rows(rows: Any, artifact_detail: str) -> list[dict[str, Any]]:
    source_rows = [dict(row) for row in rows or [] if isinstance(row, dict)]
    if artifact_detail == "full":
        return source_rows
    return [_compact_value(row) for row in source_rows]


def _compact_value(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        if key in _SCORE_MAP_FIELDS:
            return _compact_score_map(value)
        return {
            item_key: _compact_value(item_value, item_key)
            for item_key, item_value in value.items()
            if item_key not in _COMPACT_DROP_FIELDS
        }
    if isinstance(value, list):
        identity_items = compact_identity_evidence_list(value, key)
        if identity_items is not None:
            return identity_items
        return [_compact_value(item) for item in _compact_list(value, key)]
    if key in TEXT_FIELDS and isinstance(value, str):
        return value[: ARTIFACT_LIMITS["max_evidence_text_chars"]]
    return value


def _compact_list(values: list[Any], key: str) -> list[Any]:
    if key in _TRACE_FIELDS:
        return values[: ARTIFACT_LIMITS["max_trace_events"]]
    if key in _EVIDENCE_LIST_FIELDS and _looks_like_evidence_list(values):
        return values[: ARTIFACT_LIMITS["max_prediction_evidence_items"]]
    if key in _REFERENCE_LIST_FIELDS:
        return values[: ARTIFACT_LIMITS["max_prediction_evidence_items"]]
    return values


def _compact_score_map(values: dict[str, Any]) -> dict[str, Any]:
    limit = ARTIFACT_LIMITS["max_prediction_evidence_items"]
    return {
        str(key): _compact_value(value, str(key))
        for key, value in list(values.items())[:limit]
    }


def _looks_like_evidence_list(values: list[Any]) -> bool:
    return any(
        isinstance(item, dict)
        and any(field in item for field in ("evidence_id", "source_id", "file_id"))
        for item in values
    )


def _report_markdown_sections(
    summary: dict[str, Any],
    route_metric_table: list[dict[str, Any]],
) -> list[str]:
    sections: list[str] = []
    quality_rows = _quality_route_metric_table(summary)
    if quality_rows:
        sections += [
            "",
            "## Quality Route Metrics",
            "",
            *route_metrics_markdown(quality_rows),
        ]
    diagnostic_rows = _diagnostic_route_metric_table(summary)
    if diagnostic_rows:
        sections += [
            "",
            "## Diagnostic Route Metrics",
            "",
            *route_metrics_markdown(diagnostic_rows),
        ]
    if route_metric_table:
        sections += [
            "",
            "## Route Metrics",
            "",
            *route_metrics_markdown(route_metric_table),
        ]
    for title, lines in (
        ("Route Ranking", route_ranking_markdown(summary)),
        *phase3_report_sections(summary),
        ("Skipped Routes", _skipped_route_markdown(summary)),
        ("Multimodal Backend Health", _backend_health_markdown(summary)),
        ("Backend Status By Route", _backend_metadata_markdown(summary)),
        ("Generic Route Diagnostics", _route_diagnostics_markdown(summary)),
        ("Route Confusion", _route_confusion_markdown(summary)),
        ("Phase2 Failure Counts", phase2_failure_counts_markdown(summary)),
        ("Diagnostic Failure Counts", _diagnostic_failure_counts_markdown(summary)),
        ("Failure Taxonomy", failure_taxonomy_markdown(summary)),
        ("Failure Taxonomy By Route", failure_taxonomy_by_route_markdown(summary)),
        ("Routing Taxonomy", routing_taxonomy_markdown(summary)),
        ("Verifier Observability", verifier_observability_markdown(summary)),
        ("External Research Evaluators", external_evaluator_markdown(summary)),
        (
            "External Research Evaluators By Route",
            external_evaluator_by_route_markdown(summary),
        ),
    ):
        if lines:
            sections += ["", f"## {title}", "", *lines]
    return sections


def _route_diagnostics_markdown(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("dataset_route_diagnostics") or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    if not rows:
        return []
    lines = [
        "| Dataset | Route | N | Retrieved | Evidence Items | Gold Doc Hit | "
        "Gold Page Hit | Gold Span Hit | Answer Nonempty |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('num_predictions')} | "
            f"{row.get('avg_retrieved_count')} | "
            f"{row.get('avg_evidence_item_count')} | "
            f"{row.get('avg_gold_document_hit')} | "
            f"{row.get('avg_gold_page_hit')} | "
            f"{row.get('avg_gold_span_hit')} | "
            f"{row.get('avg_answer_nonempty_after_cleaning')} |"
        )
    return lines


def _route_confusion_markdown(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("route_confusion_table") or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    if not rows:
        return []
    lines = [
        "| Dataset | Route | Recommended | Selected | Count |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('recommended_route')} | "
            f"{row.get('selected_route')} | "
            f"{row.get('count')} |"
        )
    return lines


def _diagnostic_failure_counts_markdown(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("diagnostic_failure_counts") or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    if not rows:
        return []
    lines = [
        "| Dataset | Route | Failure Class | Retrieval Failure | Citation Failure | Count |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('failure_class')} | "
            f"{row.get('retrieval_failure_type')} | "
            f"{row.get('citation_failure_type')} | "
            f"{row.get('count')} |"
        )
    return lines


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = _csv_fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _csv_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    keys = list(rows[0])
    fieldnames = [key for key in _CSV_FIELD_ORDER if key in keys]
    fieldnames.extend(key for key in keys if key not in fieldnames)
    return fieldnames


def _route_metric_table(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("route_metric_table") or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _quality_route_metric_table(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("quality_route_metric_table") or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _diagnostic_route_metric_table(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("diagnostic_route_metric_table") or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _skipped_route_markdown(summary: dict[str, Any]) -> list[str]:
    lines = []
    for route in summary.get("skipped_routes") or []:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        reason = str(route.get("skip_reason") or "not_configured").strip()
        if route_id:
            lines.append(f"- `{route_id}`: {reason}")
    return lines


def _backend_metadata_markdown(summary: dict[str, Any]) -> list[str]:
    metadata = summary.get("backend_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    lines = []
    for route_id, item in metadata.items():
        if not isinstance(item, dict):
            continue
        status = str(item.get("backend_status") or "configured")
        details = _backend_detail_text(item)
        suffix = f"; {details}" if details else ""
        lines.append(f"- `{route_id}`: {status}{suffix}")
    return lines


def _backend_health_markdown(summary: dict[str, Any]) -> list[str]:
    health = summary.get("backend_health") or {}
    if not isinstance(health, dict):
        return []
    backends = health.get("backends") or {}
    if not isinstance(backends, dict):
        return []
    lines = [f"- Overall Status: `{health.get('overall_status')}`"]
    for role, item in backends.items():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        details = _backend_health_detail_text(item)
        suffix = f"; {details}" if details else ""
        lines.append(f"- `{role}`: {status}{suffix}")
    return lines


def _backend_health_detail_text(item: dict[str, Any]) -> str:
    pairs = []
    for key in ("url", "models", "model", "model_family", "failure_type"):
        value = item.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(entry) for entry in value)
        pairs.append(f"{key}=`{value}`")
    return ", ".join(pairs)


def _backend_detail_text(item: dict[str, Any]) -> str:
    ignored = {"backend_status", "missing_backends", "requires_backend_config"}
    pairs = [
        f"{key}=`{value}`"
        for key, value in sorted(item.items())
        if key not in ignored and value not in (None, "", [], {})
    ]
    return ", ".join(pairs)
