from __future__ import annotations

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

    summary = report.get("summary", {})
    config = report.get("config", {})
    predictions = report.get("predictions", [])
    documents = report.get("documents", [])
    retrieval_traces = report.get("retrieval_traces")
    if retrieval_traces is None:
        retrieval_traces = _derive_retrieval_traces(predictions)

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_jsonl(predictions_path, predictions)
    documents_path.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_jsonl(retrieval_traces_path, retrieval_traces)

    markdown = [
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
        f"- Span Recall: `{summary.get('avg_span_recall')}`",
        f"- Formula Match: `{summary.get('avg_formula_match')}`",
        f"- Numeric Match: `{summary.get('avg_numeric_match')}`",
        f"- Avg Parse Seconds: `{summary.get('avg_parse_seconds')}`",
        f"- Avg Index Seconds: `{summary.get('avg_index_seconds')}`",
        f"- Avg Retrieval Seconds: `{summary.get('avg_retrieval_seconds')}`",
        f"- Avg Generation Seconds: `{summary.get('avg_generation_seconds')}`",
        f"- Cache Mode: `{summary.get('cache_mode')}`",
        f"- Parse Cache Hit Rate: `{summary.get('parse_cache_hit_rate')}`",
        f"- Embedding Cache Hit Rate: `{summary.get('embedding_cache_hit_rate')}`",
    ]
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
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    return run_dir
