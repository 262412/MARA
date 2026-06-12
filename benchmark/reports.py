from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


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
            "agent_trace",
            "evidence_metadata",
            "claim_verification",
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
    return [
        f"# {summary.get('suite_name', suite_name)}",
        "",
        f"- Dataset: `{summary.get('dataset_name')}`",
        f"- Examples: `{summary.get('num_examples')}`",
        f"- Documents: `{summary.get('num_documents')}`",
        f"- EM: `{summary.get('avg_em')}`",
        f"- F1: `{summary.get('avg_f1')}`",
        f"- ANLS: `{summary.get('avg_anls')}`",
        f"- Page Hit: `{summary.get('avg_page_hit')}`",
        f"- Citation Recall: `{summary.get('avg_citation_recall')}`",
        f"- Element Hit: `{summary.get('avg_element_hit')}`",
        f"- Table Hit: `{summary.get('avg_table_hit')}`",
        f"- Figure Hit: `{summary.get('avg_figure_hit')}`",
        f"- Formula Hit: `{summary.get('avg_formula_hit')}`",
        f"- Slide Hit: `{summary.get('avg_slide_hit')}`",
        f"- Span Recall: `{summary.get('avg_span_recall')}`",
        f"- Formula Match: `{summary.get('avg_formula_match')}`",
        f"- Numeric Match: `{summary.get('avg_numeric_match')}`",
        f"- Abstention Rate: `{summary.get('avg_abstention_rate')}`",
        f"- False Abstention: `{summary.get('avg_false_abstention')}`",
        f"- Markdown Table Renderable: `{summary.get('avg_markdown_table_renderable')}`",
        f"- LaTeX Renderable: `{summary.get('avg_latex_renderable')}`",
        f"- Rewrite Skipped: `{summary.get('avg_rewrite_skipped')}`",
        f"- Guardrail Expectation Match: `{summary.get('avg_guardrail_expectation_match')}`",
        f"- Avg Parse Seconds: `{summary.get('avg_parse_seconds')}`",
        f"- Avg Index Seconds: `{summary.get('avg_index_seconds')}`",
        f"- Avg Retrieval Seconds: `{summary.get('avg_retrieval_seconds')}`",
        f"- Avg Generation Seconds: `{summary.get('avg_generation_seconds')}`",
        f"- Cache Mode: `{summary.get('cache_mode')}`",
        f"- Parse Cache Hit Rate: `{summary.get('parse_cache_hit_rate')}`",
        f"- Embedding Cache Hit Rate: `{summary.get('embedding_cache_hit_rate')}`",
        f"- Executed Routes: `{summary.get('num_executed_routes')}`",
        f"- Skipped Routes: `{summary.get('num_skipped_routes')}`",
    ]


def write_reports(
    report: dict[str, Any], output_dir: str | Path, suite_name: str
) -> Path:
    output_dir = Path(output_dir).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{timestamp}_{_to_slug(suite_name)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    predictions_path = run_dir / "predictions.jsonl"
    documents_path = run_dir / "documents.json"
    retrieval_traces_path = run_dir / "retrieval_traces.jsonl"
    markdown_path = run_dir / "report.md"
    route_metrics_path = run_dir / "route_metrics.csv"

    summary = report.get("summary", {})
    config = report.get("config", {})
    predictions = report.get("predictions", [])
    documents = report.get("documents", [])
    retrieval_traces = report.get("retrieval_traces")
    if retrieval_traces is None:
        retrieval_traces = _derive_retrieval_traces(predictions)

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


def _report_markdown_sections(
    summary: dict[str, Any],
    route_metric_table: list[dict[str, Any]],
) -> list[str]:
    sections: list[str] = []
    if route_metric_table:
        sections += [
            "",
            "## Route Metrics",
            "",
            *_route_metrics_markdown(route_metric_table),
        ]
    for title, lines in (
        ("Route Ranking", _route_ranking_markdown(summary)),
        ("Skipped Routes", _skipped_route_markdown(summary)),
        ("Backend Status By Route", _backend_metadata_markdown(summary)),
        ("External Research Evaluators", _external_evaluator_markdown(summary)),
        (
            "External Research Evaluators By Route",
            _external_evaluator_by_route_markdown(summary),
        ),
    ):
        if lines:
            sections += ["", f"## {title}", "", *lines]
    return sections


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _route_metric_table(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = summary.get("route_metric_table") or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _route_metrics_markdown(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Dataset | Route | N | F1 | Page Hit | Unsupported Claim Rate | Total Seconds |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('num_predictions')} | "
            f"{row.get('avg_f1')} | "
            f"{row.get('avg_page_hit')} | "
            f"{row.get('avg_unsupported_claim_rate')} | "
            f"{row.get('avg_total_seconds')} |"
        )
    return lines


def _route_ranking_markdown(summary: dict[str, Any]) -> list[str]:
    rankings = summary.get("route_rankings") or []
    lines: list[str] = []
    for ranking in rankings:
        if not isinstance(ranking, dict):
            continue
        rank_metric = str(ranking.get("rank_metric") or "score")
        for route in ranking.get("routes") or []:
            if not isinstance(route, dict):
                continue
            lines.append(
                f"{route.get('rank')}. `{route.get('route')}` "
                f"{rank_metric}=`{route.get('score')}`"
            )
    return lines


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


def _backend_detail_text(item: dict[str, Any]) -> str:
    ignored = {"backend_status", "missing_backends", "requires_backend_config"}
    pairs = [
        f"{key}=`{value}`"
        for key, value in sorted(item.items())
        if key not in ignored and value not in (None, "", [], {})
    ]
    return ", ".join(pairs)


def _external_evaluator_markdown(summary: dict[str, Any]) -> list[str]:
    metadata = summary.get("external_adapter_metric_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    lines = []
    for adapter_name, item in metadata.items():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "not_configured")
        backend = str(item.get("backend") or "").strip()
        paper_grade = item.get("paper_grade")
        metric_category = str(item.get("metric_category") or "external_metric")
        if status == "configured":
            lines.append(
                f"- `{adapter_name}`: configured via `{backend}`, "
                f"paper_grade=`{paper_grade}`, "
                f"metric_category=`{metric_category}`"
            )
        else:
            excluded = item.get("excluded_from_summary")
            lines.append(
                f"- `{adapter_name}`: {status}, " f"excluded_from_summary=`{excluded}`"
            )
    return lines


def _external_evaluator_by_route_markdown(summary: dict[str, Any]) -> list[str]:
    metadata_by_route = summary.get("external_adapter_metric_metadata_by_route") or {}
    if not isinstance(metadata_by_route, dict):
        return []
    lines = []
    for route_id, metadata in metadata_by_route.items():
        if not isinstance(metadata, dict):
            continue
        for adapter_name, item in metadata.items():
            if not isinstance(item, dict):
                continue
            lines.append(
                _external_evaluator_route_line(
                    str(route_id),
                    str(adapter_name),
                    item,
                )
            )
    return lines


def _external_evaluator_route_line(
    route_id: str,
    adapter_name: str,
    item: dict[str, Any],
) -> str:
    status = str(item.get("status") or "not_configured")
    if status == "configured":
        backend = str(item.get("backend") or "").strip()
        paper_grade = item.get("paper_grade")
        metric_category = str(item.get("metric_category") or "external_metric")
        return (
            f"- `{route_id}` / `{adapter_name}`: configured via `{backend}`, "
            f"paper_grade=`{paper_grade}`, "
            f"metric_category=`{metric_category}`"
        )
    excluded = item.get("excluded_from_summary")
    return (
        f"- `{route_id}` / `{adapter_name}`: {status}, "
        f"excluded_from_summary=`{excluded}`"
    )
