from pathlib import Path
from typing import Any, cast

from _docqa_notebook_fakes import (
    DummyNotebookService as _DummyNotebookService,
    DummyRuntime as _DummyRuntime,
    extract_json_payload as _extract_json_payload,
)
from click.testing import CliRunner
from slide_cli.docqa_cli import docqa


def test_docqa_notes_add_list_and_save_answer(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    add_result = runner.invoke(
        docqa,
        [
            "notes",
            "add",
            "conv-1",
            "--title",
            "Manual note",
            "--text",
            "Keep this source-backed note.",
            "--json",
        ],
    )
    list_result = runner.invoke(docqa, ["notes", "list", "conv-1", "--json"])
    save_result = runner.invoke(
        docqa,
        ["notes", "save-answer", "conv-1", "--title", "Last answer", "--json"],
    )

    assert add_result.exit_code == 0, add_result.output
    assert _extract_json_payload(add_result.output)["source"] == "manual"
    assert list_result.exit_code == 0, list_result.output
    notes = _extract_json_payload(list_result.output)
    assert notes[0]["title"] == "Manual note"
    assert save_result.exit_code == 0, save_result.output
    saved = _extract_json_payload(save_result.output)
    assert saved["source"] == "answer"
    assert saved["text"] == "world"


def test_docqa_notes_convert_source_indexes_note_and_selects_source(
    monkeypatch,
    tmp_path,
):
    runtime = _DummyRuntime()
    service = _DummyNotebookService(source_dir=tmp_path)
    notes = cast(list[dict[str, Any]], service.notebooks["conv-1"]["notes"])
    notes.append(
        {
            "note_id": "note-1",
            "title": "Manual note",
            "text": "Keep this source-backed note.",
            "source": "manual",
            "citation_refs": [],
            "created_at": "2026-05-31T12:00:00+00:00",
            "updated_at": "2026-05-31T12:00:00+00:00",
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        ["notes", "convert-source", "conv-1", "--note", "note-1", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["note_id"] == "note-1"
    assert payload["source_ids"] == ["file-note-1"]
    assert Path(payload["source_path"]).name == "mara-note-note-1.md"
    assert runtime.indexed_paths == [payload["source_path"]]
    assert service.notebooks["conv-1"]["selected_source_ids"] == [
        "file-1",
        "file-note-1",
    ]


def test_docqa_sources_select_and_list(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    select_result = runner.invoke(
        docqa,
        [
            "sources",
            "select",
            "conv-1",
            "--file",
            "alpha.pptx",
            "--file",
            "beta.pptx",
            "--json",
        ],
    )
    list_result = runner.invoke(docqa, ["sources", "list", "conv-1", "--json"])

    assert select_result.exit_code == 0, select_result.output
    assert _extract_json_payload(select_result.output) == {
        "conversation_id": "conv-1",
        "selected_source_ids": ["file-1", "file-2"],
    }
    assert list_result.exit_code == 0, list_result.output
    assert _extract_json_payload(list_result.output)["selected_source_ids"] == [
        "file-1",
        "file-2",
    ]


def test_docqa_sources_guide_uses_selected_sources(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    result = runner.invoke(docqa, ["sources", "guide", "conv-1", "--json"])

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload == [
        {
            "source_id": "file-1",
            "name": "alpha.pptx",
            "summary": "alpha.pptx is an indexed pdf source.",
            "key_topics": ["alpha"],
            "suggested_questions": ["What are the key points in alpha.pptx?"],
            "metadata": {"tokens": 1200},
        }
    ]


def test_docqa_artifacts_list_and_show(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    service.notebooks["conv-1"]["artifacts"].append(
        {
            "artifact_id": "artifact-1",
            "type": "quiz",
            "payload": {"questions": []},
            "created_at": "2026-05-31T12:06:00+00:00",
        }
    )
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    list_result = runner.invoke(docqa, ["artifacts", "list", "conv-1", "--json"])
    show_result = runner.invoke(
        docqa,
        ["artifacts", "show", "conv-1", "--artifact", "artifact-1", "--json"],
    )

    assert list_result.exit_code == 0, list_result.output
    assert _extract_json_payload(list_result.output)[0]["artifact_id"] == "artifact-1"
    assert show_result.exit_code == 0, show_result.output
    assert _extract_json_payload(show_result.output) == {
        "artifact_id": "artifact-1",
        "type": "quiz",
        "payload": {"questions": []},
        "created_at": "2026-05-31T12:06:00+00:00",
    }


def test_docqa_artifacts_generate_uses_selected_sources_and_saves_artifact(
    monkeypatch,
):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_notebook_cli._notebook_service",
        lambda: service,
    )

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "artifacts",
            "generate",
            "conv-1",
            "--type",
            "quiz",
            "--prompt",
            "Generate a source-grounded quiz.",
            "--agent-mode",
            "thorough",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    request = runtime.requests[0]
    assert request.conversation_id == "conv-1"
    assert request.selected_file_ids == ["file-1"]
    assert request.reasoning_type == "mara"
    assert request.task_type == "quiz"
    assert request.artifact_type == "quiz"
    assert request.agent_mode == "thorough"
    payload = _extract_json_payload(result.output)
    assert payload["artifact_id"] == "artifact-1"
    assert payload["type"] == "quiz"
    assert payload["status"] == "ready"
    assert payload["title"] == "Quiz"
    assert payload["payload"] == {"type": "quiz", "multiple_choice": []}
    assert payload["created_at"] == "2026-05-31T12:06:00+00:00"
    assert service.notebooks["conv-1"]["artifacts"][0]["type"] == "quiz"


def test_docqa_artifacts_generate_uses_notebook_note_content(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
    service.notebooks["conv-1"]["notes"].append(
        {
            "note_id": "note-1",
            "title": "Grounding note",
            "text": "Use this note as study guide evidence.",
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
            "generate",
            "conv-1",
            "--type",
            "study_guide",
            "--note",
            "note-1",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    request = runtime.requests[0]
    assert request.note_ids == ["note-1"]
    assert "Notebook notes:" in request.prompt
    assert "Grounding note" in request.prompt
    assert "Use this note as study guide evidence." in request.prompt
    artifact = _extract_json_payload(result.output)
    assert artifact["source_scope"]["note_ids"] == ["note-1"]


def test_docqa_artifacts_generate_rejects_missing_note(monkeypatch):
    runtime = _DummyRuntime()
    service = _DummyNotebookService()
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
            "study_guide",
            "--note",
            "missing-note",
        ],
    )

    assert result.exit_code != 0
    assert "Notebook note does not exist: missing-note" in result.output
    assert runtime.requests == []
