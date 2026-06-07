from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def evaluate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    source_scope = artifact.get("source_scope") if isinstance(artifact, dict) else {}
    source_scope = source_scope if isinstance(source_scope, dict) else {}
    citations = _records(artifact.get("citations"))
    source_ids = _unique_text(source_scope.get("source_ids", []))
    cited_source_ids = _cited_source_ids(citations)
    cited_in_scope = [item for item in cited_source_ids if item in source_ids]
    coverage = _coverage(cited_in_scope, source_ids, citations)
    report = {
        "artifact": _artifact_summary(artifact),
        "document_scope": {
            "mode": str(source_scope.get("mode") or "document"),
            "source_count": len(source_ids),
            "citation_count": len(citations),
            "cited_source_count": len(cited_in_scope or cited_source_ids),
            "export_count": len(_records(artifact.get("exports"))),
        },
        "metric_tiers": {
            "proxy_metric": {
                "citation_coverage": coverage,
                "groundedness_proxy": _groundedness_proxy(artifact, citations),
                "artifact_usefulness_proxy": _artifact_usefulness_proxy(
                    artifact, citations
                ),
                "latency_seconds": _latency_seconds(artifact.get("generation")),
            },
            "external_metric": {
                "status": "not_configured",
                "adapters": [],
            },
            "paper_grade_metric": {
                "status": "not_claimed",
                "reason": (
                    "This report contains local proxy metrics only; run external "
                    "benchmark adapters before claiming paper-grade evaluation."
                ),
            },
        },
    }
    return deepcopy(report)


def evaluate_artifact_collection(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    artifact_records = _records(artifacts)
    artifact_reports = [evaluate_artifact(artifact) for artifact in artifact_records]
    format_summary = _source_format_summary(artifact_records)
    proxy_metrics = [
        report["metric_tiers"]["proxy_metric"] for report in artifact_reports
    ]
    report = {
        "artifact_count": len(artifact_records),
        "artifacts": [report["artifact"] for report in artifact_reports],
        "document_scope": {
            "mode": "collection",
            "source_count": len(_collection_source_ids(artifact_records)),
            "citation_count": sum(
                len(_records(artifact.get("citations")))
                for artifact in artifact_records
            ),
            "cited_source_count": sum(
                item["source_count"] for item in format_summary.values()
            ),
            "export_count": sum(
                len(_records(artifact.get("exports"))) for artifact in artifact_records
            ),
            "source_format_count": len(format_summary),
        },
        "source_format_summary": format_summary,
        "metric_tiers": {
            "proxy_metric": {
                "mean_citation_coverage": _mean(
                    metric.get("citation_coverage") for metric in proxy_metrics
                ),
                "mean_groundedness_proxy": _mean(
                    metric.get("groundedness_proxy") for metric in proxy_metrics
                ),
                "mean_artifact_usefulness_proxy": _mean(
                    metric.get("artifact_usefulness_proxy") for metric in proxy_metrics
                ),
                "mean_latency_seconds": _mean(
                    metric.get("latency_seconds") for metric in proxy_metrics
                ),
            },
            "external_metric": {
                "status": "not_configured",
                "adapters": [],
            },
            "paper_grade_metric": {
                "status": "not_claimed",
                "reason": (
                    "This report summarizes local proxy metrics only; run external "
                    "benchmark adapters before claiming paper-grade evaluation."
                ),
            },
        },
    }
    return deepcopy(report)


def write_artifact_evaluation_report(
    report: dict[str, Any],
    output_path: str | Path,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def _artifact_summary(artifact: dict[str, Any]) -> dict[str, str]:
    return {
        "artifact_id": str(artifact.get("artifact_id") or ""),
        "type": str(artifact.get("type") or ""),
        "title": str(artifact.get("title") or artifact.get("type") or "Artifact"),
        "status": str(artifact.get("status") or ""),
    }


def _collection_source_ids(artifacts: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for artifact in artifacts:
        source_scope = artifact.get("source_scope")
        if isinstance(source_scope, dict):
            refs.extend(_unique_text(source_scope.get("source_ids", [])))
        refs.extend(_cited_source_ids(_records(artifact.get("citations"))))
    return _unique_text(refs)


def _source_format_summary(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    counters: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        artifact_formats: set[str] = set()
        for citation in _records(artifact.get("citations")):
            source_format = _source_format(citation)
            artifact_formats.add(source_format)
            entry = counters.setdefault(
                source_format,
                {
                    "artifact_count": 0,
                    "citation_count": 0,
                    "source_refs": set(),
                },
            )
            entry["citation_count"] += 1
            entry["source_refs"].add(_citation_source_ref(citation))
        for source_format in artifact_formats:
            counters[source_format]["artifact_count"] += 1
    return {
        source_format: {
            "artifact_count": counters[source_format]["artifact_count"],
            "citation_count": counters[source_format]["citation_count"],
            "source_count": len(counters[source_format]["source_refs"]),
        }
        for source_format in sorted(counters)
    }


def _source_format(citation: dict[str, Any]) -> str:
    explicit_format = str(
        citation.get("source_format") or citation.get("format") or ""
    ).strip()
    if explicit_format:
        return _normalized_source_format(explicit_format)
    for key in ("source_name", "source_path", "path", "file_name", "filename", "url"):
        value = str(citation.get(key) or "").strip()
        if value:
            suffix = Path(value.split("?", 1)[0].split("#", 1)[0]).suffix
            return _normalized_source_format(suffix.lstrip(".") or value)
    return "unknown"


def _normalized_source_format(value: str) -> str:
    source_format = value.strip().lower().lstrip(".")
    if source_format in {"ppt", "pptx"}:
        return "pptx"
    if source_format in {"doc", "docx"}:
        return "docx"
    if source_format in {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff"}:
        return "image"
    if source_format in {"xls", "xlsx", "csv", "tsv"}:
        return "table"
    if source_format in {"md", "markdown", "txt", "html"}:
        return "text"
    return source_format or "unknown"


def _citation_source_ref(citation: dict[str, Any]) -> str:
    for key in ("source_id", "source_name", "source_path", "path", "file_name"):
        value = str(citation.get(key) or "").strip()
        if value:
            return value
    return str(citation.get("citation_id") or "unknown")


def _mean(values: Any) -> float | None:
    numbers = [float(value) for value in values if value not in (None, "")]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 4)


def _records(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _cited_source_ids(citations: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for citation in citations:
        refs.extend(_unique_text(citation.get("source_ids", [])))
        source_id = str(citation.get("source_id") or "").strip()
        if source_id:
            refs.append(source_id)
    return _unique_text(refs)


def _coverage(
    cited_in_scope: list[str],
    source_ids: list[str],
    citations: list[dict[str, Any]],
) -> float:
    if source_ids:
        return round(len(cited_in_scope) / len(source_ids), 4)
    return 1.0 if citations else 0.0


def _groundedness_proxy(
    artifact: dict[str, Any],
    citations: list[dict[str, Any]],
) -> float:
    if not _has_payload(artifact):
        return 0.0
    return 1.0 if citations else 0.25


def _artifact_usefulness_proxy(
    artifact: dict[str, Any],
    citations: list[dict[str, Any]],
) -> float:
    checks = [
        str(artifact.get("status") or "") == "ready",
        _has_payload(artifact),
        bool(citations),
        bool(str(artifact.get("title") or artifact.get("type") or "").strip()),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 4)


def _latency_seconds(generation: Any) -> float | None:
    if not isinstance(generation, dict):
        return None
    parameters = generation.get("parameters")
    value = generation.get("latency_seconds")
    if value is None and isinstance(parameters, dict):
        value = parameters.get("latency_seconds")
    if value in (None, ""):
        return None
    return float(str(value))


def _has_payload(artifact: dict[str, Any]) -> bool:
    payload = artifact.get("payload")
    return payload not in (None, "", [], {})


def _unique_text(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    output: list[str] = []
    for value in items:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
