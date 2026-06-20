from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import prediction_diagnostics
from .indexed_citations import indexed_inline_citations
from .mara_oriented_scores import (
    add_mara_oriented_metrics,
    promote_external_primary_score,
)
from .reports import write_reports
from .research_evaluators import external_research_adapter_metrics
from .scoring import normalize_operational_fields, score_prediction
from .summary import add_mara_summary_fields


def rescore_artifact_run(
    run_dir: str | Path,
    output_dir: str | Path,
    *,
    suite_name: str | None = None,
    artifact_detail: str = "compact",
    external_evaluators: dict[str, str] | None = None,
) -> Path:
    source_dir = Path(run_dir).resolve()
    summary = _read_json(source_dir / "summary.json")
    dataset_name = str(summary.get("dataset_name") or "unknown")
    predictions = _read_jsonl(source_dir / "predictions.jsonl")
    evaluator_route = _external_evaluator_route(external_evaluators)
    for prediction in predictions:
        _rescore_prediction_base_metrics(prediction)
        add_mara_oriented_metrics(prediction, dataset_name=dataset_name)
        if evaluator_route:
            (
                prediction["external_adapter_metrics"],
                prediction["external_adapter_metric_metadata"],
            ) = external_research_adapter_metrics(prediction, evaluator_route)
            promote_external_primary_score(prediction, dataset_name=dataset_name)

    rescored_summary = add_mara_summary_fields(summary, predictions)
    if suite_name:
        rescored_summary["suite_name"] = suite_name
    rescored_summary["mara_rescore_source_run_dir"] = str(source_dir)
    rescored_summary["mara_rescore_mode"] = "dataset_native_v1"
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


def _rescore_prediction_base_metrics(prediction: dict[str, Any]) -> None:
    _prepare_prediction_defaults(prediction)
    _refresh_indexed_inline_citations(prediction)
    normalize_operational_fields(prediction)
    prediction["metrics"] = score_prediction(prediction)
    prediction["diagnostics"] = prediction_diagnostics(prediction)


def _prepare_prediction_defaults(prediction: dict[str, Any]) -> None:
    prediction.setdefault("gold_answers", [])
    prediction.setdefault("predicted_answer", "")
    prediction.setdefault("gold_pages", [])
    prediction.setdefault("predicted_pages", [])
    prediction.setdefault("gold_sources", [])
    prediction.setdefault("predicted_sources", [])
    prediction.setdefault("predicted_citations", [])
    prediction.setdefault("scored_predicted_sources", [])
    prediction.setdefault("gold_evidence", [])
    prediction.setdefault("expected_formats", [])
    prediction.setdefault("expected_guardrails", {})
    prediction.setdefault("claim_verification", {})
    prediction.setdefault("verify_decision", {})
    prediction.setdefault("guardrail_decision", {})
    prediction.setdefault("evidence_metadata", {})
    prediction.setdefault("evidence_bundle", {})
    prediction.setdefault("retrieved_hits", [])


def _refresh_indexed_inline_citations(prediction: dict[str, Any]) -> None:
    if prediction.get("predicted_citations"):
        return
    citations = indexed_inline_citations(
        str(prediction.get("predicted_answer") or ""),
        list(prediction.get("retrieved_hits") or []),
    )
    if citations:
        prediction["predicted_citations"] = citations


def rescore_artifact_runs(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    suite_prefix: str = "rescored",
    artifact_detail: str = "compact",
    external_evaluators: dict[str, str] | None = None,
) -> list[Path]:
    runs = _discover_rescorable_runs(Path(input_dir))
    return [
        rescore_artifact_run(
            run_dir,
            output_dir,
            suite_name=f"{suite_prefix}-{run_dir.name}",
            artifact_detail=artifact_detail,
            external_evaluators=external_evaluators,
        )
        for run_dir in runs
    ]


def _discover_rescorable_runs(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Artifact input directory does not exist: {input_dir}")
    return [
        path
        for path in sorted(input_dir.iterdir())
        if path.is_dir() and _is_rescorable_run(path)
    ]


def _is_rescorable_run(path: Path) -> bool:
    summary_path = path / "summary.json"
    if not summary_path.exists() or not (path / "predictions.jsonl").exists():
        return False
    summary = _read_json(summary_path)
    return "mara_rescore_source_run_dir" not in summary


def _external_evaluator_route(
    external_evaluators: dict[str, str] | None,
) -> dict[str, Any]:
    if not external_evaluators:
        return {}
    return {"external_evaluators": dict(external_evaluators)}


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
