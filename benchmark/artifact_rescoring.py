from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mara_oriented_scores import add_mara_oriented_metrics
from .reports import write_reports
from .summary import add_mara_summary_fields


def rescore_artifact_run(
    run_dir: str | Path,
    output_dir: str | Path,
    *,
    suite_name: str | None = None,
    artifact_detail: str = "compact",
) -> Path:
    source_dir = Path(run_dir).resolve()
    summary = _read_json(source_dir / "summary.json")
    dataset_name = str(summary.get("dataset_name") or "unknown")
    predictions = _read_jsonl(source_dir / "predictions.jsonl")
    for prediction in predictions:
        add_mara_oriented_metrics(prediction, dataset_name=dataset_name)

    rescored_summary = add_mara_summary_fields(summary, predictions)
    rescored_summary["mara_rescore_source_run_dir"] = str(source_dir)
    rescored_summary["mara_rescore_mode"] = "deterministic_v1"
    report = {
        "summary": rescored_summary,
        "predictions": predictions,
        "documents": _read_optional_json(source_dir / "documents.json", default=[]),
    }
    retrieval_traces = _read_optional_jsonl(source_dir / "retrieval_traces.jsonl")
    if retrieval_traces is not None:
        report["retrieval_traces"] = retrieval_traces
    return write_reports(
        report,
        output_dir,
        suite_name or str(summary.get("suite_name") or "rescored-artifact"),
        artifact_detail=artifact_detail,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _read_optional_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        dict(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    return _read_jsonl(path)
