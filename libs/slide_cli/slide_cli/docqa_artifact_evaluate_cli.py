from __future__ import annotations

from typing import Any

import click

from . import docqa_notebook_cli as notebook_cli


def register_artifact_evaluate_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("evaluate")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", default="")
    @click.option("--output", "output_path", default="", help="JSON report path.")
    @notebook_cli._json_option
    def artifacts_evaluate(
        conversation_id,
        artifact_id,
        output_path,
        json_output,
    ):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        service = notebook_cli._notebook_service()
        notebook = service.get_notebook(conversation_id)
        artifact = _notebook_artifact(notebook, artifact_id) if artifact_id else None
        if artifact_id and artifact is None:
            raise click.ClickException(f"Artifact '{artifact_id}' does not exist.")
        report = (
            _evaluate_artifact(artifact)
            if artifact_id and artifact is not None
            else _evaluate_artifact_collection(_notebook_artifacts(notebook))
        )
        payload = {
            "conversation_id": conversation_id,
            "artifact_id": str(artifact_id or ""),
            "report": report,
        }
        if output_path:
            payload["output_path"] = str(
                _write_artifact_evaluation_report(report, output_path)
            )
        if json_output:
            notebook_cli._echo_json(payload)
            return
        _print_artifact_evaluation_summary(payload)


def _notebook_artifacts(notebook: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = notebook.get("artifacts", [])
    return [dict(item) for item in artifacts if isinstance(item, dict)]


def _notebook_artifact(
    notebook: dict[str, Any],
    artifact_id: str,
) -> dict[str, Any] | None:
    lookup = str(artifact_id or "").strip()
    for artifact in _notebook_artifacts(notebook):
        if str(artifact.get("artifact_id") or "") == lookup:
            return artifact
    return None


def _evaluate_artifact(artifact):
    from ktem.docqa.artifact_evaluation import evaluate_artifact

    return evaluate_artifact(artifact)


def _evaluate_artifact_collection(artifacts):
    from ktem.docqa.artifact_evaluation import evaluate_artifact_collection

    return evaluate_artifact_collection(artifacts)


def _write_artifact_evaluation_report(report, output_path):
    from ktem.docqa.artifact_evaluation import write_artifact_evaluation_report

    return write_artifact_evaluation_report(report, output_path)


def _print_artifact_evaluation_summary(payload: dict[str, Any]) -> None:
    report = payload.get("report", {})
    tiers = report.get("metric_tiers", {}) if isinstance(report, dict) else {}
    proxy = tiers.get("proxy_metric", {}) if isinstance(tiers, dict) else {}
    metric = "mean_citation_coverage"
    if "citation_coverage" in proxy:
        metric = "citation_coverage"
    notebook_cli._echo_text(f"proxy_metric.{metric}={proxy.get(metric, 0.0)}")
    output_path = payload.get("output_path")
    if output_path:
        notebook_cli._echo_text(str(output_path))
