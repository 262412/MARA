from typing import Any, cast

from click.testing import CliRunner
from slide_cli.docqa_cli import docqa
from test_docqa_notebook_cli import (
    _DummyNotebookService,
    _DummyRuntime,
    _extract_json_payload,
)


class _ArtifactNotebookService(_DummyNotebookService):
    def delete_artifact_from_conversation(
        self,
        conversation_id: str,
        artifact_id: str,
    ) -> dict[str, Any]:
        artifacts = cast(
            list[dict[str, Any]],
            self.notebooks[conversation_id]["artifacts"],
        )
        for index, artifact in enumerate(artifacts):
            if artifact.get("artifact_id") == artifact_id:
                return artifacts.pop(index)
        raise ValueError(f"Artifact '{artifact_id}' does not exist.")

    def record_artifact_export_to_conversation(
        self,
        conversation_id: str,
        artifact_id: str,
        *,
        export_format: str,
        path: str,
    ) -> dict[str, Any]:
        for artifact in self.notebooks[conversation_id]["artifacts"]:
            if artifact.get("artifact_id") == artifact_id:
                artifact.setdefault("exports", []).append(
                    {
                        "format": export_format,
                        "path": path,
                        "created_at": "2026-05-31T12:07:00+00:00",
                    }
                )
                artifact["updated_at"] = "2026-05-31T12:07:00+00:00"
                return artifact
        raise ValueError(f"Artifact '{artifact_id}' does not exist.")


def _add_cross_format_artifacts(service: _ArtifactNotebookService) -> None:
    service.notebooks["conv-1"]["artifacts"].extend(
        [
            {
                "artifact_id": "artifact-1",
                "type": "briefing_doc",
                "title": "Launch briefing",
                "status": "ready",
                "source_scope": {
                    "mode": "multi-document",
                    "source_ids": ["file-1", "file-2"],
                },
                "payload": {"sections": [{"summary": "Grounded."}]},
                "citations": [
                    {
                        "citation_id": "c1",
                        "source_id": "file-1",
                        "source_name": "launch.pdf",
                    },
                    {
                        "citation_id": "c2",
                        "source_id": "file-2",
                        "source_name": "deck.pptx",
                    },
                ],
            },
            {
                "artifact_id": "artifact-2",
                "type": "study_guide",
                "title": "Study guide",
                "status": "ready",
                "source_scope": {
                    "mode": "multi-document",
                    "source_ids": ["file-3", "file-4"],
                },
                "payload": {"overview": "Grounded overview."},
                "citations": [
                    {
                        "citation_id": "c3",
                        "source_id": "file-3",
                        "source_name": "brief.docx",
                    },
                    {
                        "citation_id": "c4",
                        "source_id": "file-4",
                        "source_name": "page.png",
                    },
                ],
            },
        ]
    )


def test_docqa_artifacts_export_writes_file_and_records_metadata(
    monkeypatch,
    tmp_path,
):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "study_guide",
            "title": "Study Guide",
            "payload": {"overview": "Grounded overview"},
            "citations": [{"citation_id": "c1", "source_id": "file-1"}],
            "exports": [],
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )
    output = tmp_path / "study-guide.md"

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "export",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--format",
            "md",
            "--output",
            str(output),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["output_path"] == str(output)
    assert "Grounded overview" in output.read_text(encoding="utf-8")
    assert service.notebooks["conv-1"]["artifacts"][0]["exports"] == [
        {
            "format": "md",
            "path": str(output),
            "created_at": "2026-05-31T12:07:00+00:00",
        }
    ]


def test_docqa_artifacts_show_renders_pretty_markdown(monkeypatch):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "study_guide",
            "title": "Study guide",
            "payload": {"overview": "Grounded overview"},
            "citations": [{"citation_id": "c1", "source_id": "file-1"}],
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "show",
            "conv-1",
            "--artifact",
            "artifact-1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "# Study guide" in result.output
    assert "## Overview" in result.output
    assert "Grounded overview" in result.output
    assert "## Citations" in result.output


def test_docqa_artifacts_export_reports_media_adapter_requirement(monkeypatch):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "audio_overview",
            "title": "Audio",
            "payload": {"media_status": "script_only", "script": []},
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "export",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--format",
            "mp3",
        ],
    )

    assert result.exit_code != 0
    assert "requires a configured media export adapter" in result.output


def test_docqa_artifacts_export_uses_configured_media_adapter(
    monkeypatch,
    tmp_path,
):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "audio_overview",
            "title": "Audio",
            "payload": {"media_status": "script_only", "script": []},
            "exports": [],
        }
    )

    def media_adapter(_artifact, _export_format, output_path):
        output_path.write_bytes(b"configured-audio")
        return output_path

    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "ktem.docqa.artifact_exports.configured_media_export_adapter",
        lambda: media_adapter,
    )
    output = tmp_path / "overview.mp3"

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "export",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--format",
            "mp3",
            "--output",
            str(output),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.read_bytes() == b"configured-audio"
    payload = _extract_json_payload(result.output)
    assert payload["format"] == "mp3"
    assert payload["output_path"] == str(output)
    assert service.notebooks["conv-1"]["artifacts"][0]["exports"] == [
        {
            "format": "mp3",
            "path": str(output),
            "created_at": "2026-05-31T12:07:00+00:00",
        }
    ]


def test_docqa_artifacts_evaluate_reports_proxy_metric_tiers(
    monkeypatch,
    tmp_path,
):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "briefing_doc",
            "title": "Launch briefing",
            "status": "ready",
            "source_scope": {
                "mode": "multi-document",
                "source_ids": ["file-1", "file-2"],
            },
            "payload": {
                "sections": [
                    {
                        "title": "Finding",
                        "summary": "Source-grounded evidence.",
                        "source_ids": ["file-1"],
                    }
                ]
            },
            "citations": [{"citation_id": "c1", "source_id": "file-1"}],
            "exports": [],
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )
    output = tmp_path / "artifact-evaluation.json"

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "evaluate",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--output",
            str(output),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["output_path"] == str(output)
    assert payload["report"]["metric_tiers"]["proxy_metric"]["citation_coverage"] == 0.5
    assert (
        payload["report"]["metric_tiers"]["external_metric"]["status"]
        == "not_configured"
    )
    assert (
        payload["report"]["metric_tiers"]["paper_grade_metric"]["status"]
        == "not_claimed"
    )
    assert "proxy_metric" in output.read_text(encoding="utf-8")


def test_docqa_artifacts_evaluate_without_artifact_reports_collection_summary(
    monkeypatch,
    tmp_path,
):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    _add_cross_format_artifacts(service)
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )
    output = tmp_path / "artifact-evaluation.json"

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "evaluate",
            "conv-1",
            "--output",
            str(output),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["artifact_id"] == ""
    assert payload["output_path"] == str(output)
    assert payload["report"]["artifact_count"] == 2
    assert payload["report"]["source_format_summary"]["pdf"]["citation_count"] == 1
    assert payload["report"]["source_format_summary"]["pptx"]["citation_count"] == 1
    assert payload["report"]["source_format_summary"]["docx"]["citation_count"] == 1
    assert payload["report"]["source_format_summary"]["image"]["citation_count"] == 1
    assert "source_format_summary" in output.read_text(encoding="utf-8")

    text_result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "evaluate",
            "conv-1",
        ],
    )

    assert text_result.exit_code == 0, text_result.output
    assert "proxy_metric.mean_citation_coverage=1.0" in text_result.output


def test_docqa_artifacts_delete_removes_saved_artifact(monkeypatch):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {"artifact_id": "artifact-1", "type": "quiz", "payload": {}}
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "delete",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        _extract_json_payload(result.output)["deleted"]["artifact_id"] == "artifact-1"
    )
    assert service.notebooks["conv-1"]["artifacts"] == []


def test_docqa_artifacts_save_note_creates_notebook_note(monkeypatch):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "briefing_doc",
            "title": "Launch briefing",
            "prompt": "Create an executive briefing.",
            "payload": {"sections": [{"title": "Finding", "summary": "Grounded."}]},
            "citations": [
                {
                    "citation_id": "c1",
                    "source_name": "launch.pdf",
                    "page_label": "3",
                }
            ],
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "save-note",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["artifact_id"] == "artifact-1"
    assert payload["note"]["title"] == "Launch briefing"
    note = service.notebooks["conv-1"]["notes"][0]
    assert "Create an executive briefing." in note["text"]
    assert "launch.pdf p.3" in note["text"]


def test_docqa_artifacts_generate_canonicalizes_multi_document_source_scope(
    monkeypatch,
):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "generate",
            "conv-1",
            "--type",
            "quiz",
            "--scope",
            "multi-document",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    artifact = _extract_json_payload(result.output)
    assert artifact["source_scope"] == {
        "mode": "multi_document",
        "source_ids": ["file-1"],
    }
    assert service.notebooks["conv-1"]["artifacts"][0]["source_scope"] == {
        "mode": "multi_document",
        "source_ids": ["file-1"],
    }


def test_docqa_artifacts_regenerate_uses_saved_scope_and_prompt(monkeypatch):
    runtime = _DummyRuntime()
    service = _ArtifactNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "quiz",
            "prompt": "Original quiz prompt.",
            "source_scope": {
                "mode": "document",
                "source_ids": ["file-1"],
                "note_ids": ["note-1"],
            },
            "payload": {"multiple_choice": []},
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    result = CliRunner().invoke(
        docqa,
        [
            "artifacts",
            "regenerate",
            "conv-1",
            "--artifact",
            "artifact-1",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    request = runtime.requests[0]
    assert request.prompt == "Original quiz prompt."
    assert request.selected_file_ids == ["file-1"]
    assert request.note_ids == ["note-1"]
    assert request.artifact_type == "quiz"
    regenerated = _extract_json_payload(result.output)["regenerated"]
    assert regenerated["type"] == "quiz"
    assert regenerated["source_scope"]["note_ids"] == ["note-1"]
