from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from .artifact_publication import (
    atomic_write_json,
    atomic_write_text,
    normalize_artifact_requirements,
    publish_artifact_contract,
    verify_artifact_contract,
)
from .qasper_semantic_debug_artifact import (
    qasper_semantic_debug_rows,
    qasper_semantic_debug_summary,
)


def semantic_debug_artifacts(
    report: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> tuple[list[str], bool, list[dict[str, Any]]]:
    requirements = run_artifact_requirements(report)
    required = "semantic_debug_traces.jsonl" in requirements
    rows = qasper_semantic_debug_rows(
        predictions,
        include_missing=required,
        run_context=_semantic_debug_run_context(report),
    )
    return requirements, required, rows


def _semantic_debug_run_context(report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(report.get("summary") or {})
    return {
        "worktree_path": str(Path(__file__).resolve().parents[1]),
        "run_provenance": dict(summary.get("run_provenance") or {}),
        "backend_metadata": dict(summary.get("backend_metadata") or {}),
    }


def report_context(
    report: dict[str, Any],
    artifact_detail: str,
    artifact_limits: dict[str, int],
) -> tuple[
    list[dict[str, Any]],
    list[str],
    bool,
    list[dict[str, Any]],
    dict[str, Any],
    Any,
]:
    source_predictions = [
        dict(row)
        for row in report.get("predictions", []) or []
        if isinstance(row, dict)
    ]
    requirements, semantic_required, semantic_rows = semantic_debug_artifacts(
        report,
        source_predictions,
    )
    summary = {
        **dict(report.get("summary", {}) or {}),
        "artifact_detail": artifact_detail,
        "artifact_limits": dict(artifact_limits),
    }
    if semantic_rows or semantic_required:
        summary.update(qasper_semantic_debug_summary(semantic_rows))
    if requirements:
        summary["artifact_requirements"] = list(requirements)
    return (
        source_predictions,
        requirements,
        semantic_required,
        semantic_rows,
        summary,
        report.get("config", {}),
    )


def run_artifact_requirements(report: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for source in (report, report.get("summary", {}), report.get("config", {})):
        if not isinstance(source, dict):
            continue
        for key in ("run_requirements", "artifact_requirements"):
            if key in source:
                values.append(source[key])
        if source.get("required_artifacts") is not None:
            values.append({"required_artifacts": source["required_artifacts"]})
        for key in (
            "require_semantic_debug_trace",
            "require_semantic_debug_traces",
            "semantic_debug_trace_required",
            "semantic_debug_traces_required",
            "formal_audit_required",
            "require_formal_audit",
            "require_contract_smoke_audit",
            "require_contract_smoke",
        ):
            if source.get(key) is not None:
                values.append({key: source[key]})
    if os.environ.get("MARA_REQUIRE_SEMANTIC_DEBUG_TRACE") == "1":
        values.append({"semantic_debug_traces": True})
    if os.environ.get("MARA_REQUIRE_CONTRACT_SMOKE") == "1":
        values.append({"contract_smoke_audit": True})
        if os.environ.get("MARA_CONTRACT_SMOKE_SUITE_KIND") == "qasper_debug":
            values.append({"semantic_debug_traces": True})
    requirements: list[str] = []
    for value in values:
        requirements.extend(normalize_artifact_requirements(value))
    return list(dict.fromkeys(requirements))


def normalize_artifact_detail(artifact_detail: str) -> str:
    value = str(artifact_detail or "compact").strip().lower()
    if value not in {"compact", "full"}:
        raise ValueError("artifact_detail must be one of 'compact' or 'full'.")
    return value


def write_report_artifacts(
    artifact_paths: tuple[Path, Path, Path, Path, Path],
    predictions: list[dict[str, Any]],
    semantic_debug_rows: list[dict[str, Any]],
    semantic_debug_required: bool,
    documents: list[dict[str, Any]],
    retrieval_traces: list[dict[str, Any]],
    summary: dict[str, Any],
    write_csv: Callable[[Path, list[dict[str, Any]]], None],
    write_jsonl: Callable[[Path, list[dict[str, Any]]], None],
) -> list[dict[str, Any]]:
    (
        predictions_path,
        semantic_debug_path,
        documents_path,
        retrieval_traces_path,
        route_metrics_path,
    ) = artifact_paths
    write_jsonl(predictions_path, predictions)
    if semantic_debug_rows:
        write_jsonl(semantic_debug_path, semantic_debug_rows)
    elif semantic_debug_required:
        write_jsonl(semantic_debug_path, [])
    atomic_write_json(documents_path, documents)
    write_jsonl(retrieval_traces_path, retrieval_traces)
    route_metric_table = [
        dict(row)
        for row in summary.get("route_metric_table") or []
        if isinstance(row, dict)
    ]
    if route_metric_table:
        write_csv(route_metrics_path, route_metric_table)
    return route_metric_table


def write_report_outputs(
    run_dir: Path,
    markdown_path: Path,
    summary_path: Path,
    summary: dict[str, Any],
    suite_name: str,
    config: Any,
    route_metric_table: list[dict[str, Any]],
    semantic_debug_rows: list[dict[str, Any]],
    run_requirements: list[str],
    summary_markdown: Callable[..., list[str]],
    report_sections: Callable[..., list[str]],
    first_present: Callable[..., Any],
) -> None:
    markdown = summary_markdown(summary, suite_name)
    for label, key in (("Engine", "engine"), ("Route", "route"), ("Scope", "scope")):
        value = first_present(summary, config, key=key)
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
    if semantic_debug_rows:
        markdown.append("- Semantic Debug Traces: `semantic_debug_traces.jsonl`")
    markdown += report_sections(summary, route_metric_table)
    atomic_write_text(markdown_path, "\n".join(markdown) + "\n")
    atomic_write_json(summary_path, summary)
    publish_report_artifacts(run_dir, run_requirements)


def publish_report_artifacts(
    run_dir: str | Path,
    run_requirements: list[str],
) -> dict[str, Any]:
    marker = publish_artifact_contract(
        run_dir,
        run_requirements=run_requirements,
    )
    if marker["complete"]:
        verify_artifact_contract(run_dir)
    return marker


def required_artifact_violations(
    run_dir: Path,
    predictions: list[dict[str, Any]],
) -> list[str]:
    manifest_path = run_dir / "artifact_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        if isinstance(value, dict):
            manifest = value
    required = set(normalize_artifact_requirements(manifest.get("run_requirements")))
    required.update(normalize_artifact_requirements(manifest.get("required_files")))
    if os.environ.get("MARA_REQUIRE_SEMANTIC_DEBUG_TRACE") == "1":
        required.add("semantic_debug_traces.jsonl")
    semantic_name = "semantic_debug_traces.jsonl"
    if semantic_name not in required:
        return []
    semantic_path = run_dir / semantic_name
    if not semantic_path.is_file():
        return ["semantic_debug_trace_missing"]
    with semantic_path.open("r", encoding="utf-8") as handle:
        actual = sum(1 for line in handle if line.strip())
    expected = len(predictions)
    if expected > 0 and actual != expected:
        return [f"semantic_debug_trace_count_mismatch:{actual}/{expected}"]
    return []
