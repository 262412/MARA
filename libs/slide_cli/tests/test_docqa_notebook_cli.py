import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from click.testing import CliRunner
from slide_cli.docqa_cli import docqa


class _DummyFileRecord:
    def __init__(self, file_id: str, name: str):
        self.file_id = file_id
        self.name = name
        self.tokens = 1200 if file_id == "file-1" else 900
        self.size = 4096
        self.loader = "pdf"
        self.path = f"D:/docs/{name}"
        self.date_created = "2026-05-31T12:00:00"


class _DummyIndexResult:
    def __init__(
        self,
        successes: list[dict[str, Any]] | None = None,
        failures: list[dict[str, Any]] | None = None,
        debug_messages: list[str] | None = None,
    ):
        self.successes = list(successes or [])
        self.failures = list(failures or [])
        self.debug_messages = list(debug_messages or [])

    def as_dict(self):
        return {
            "successes": self.successes,
            "failures": self.failures,
            "debug_messages": self.debug_messages,
        }


class _DummyRuntime:
    def __init__(self):
        self.files = [
            _DummyFileRecord("file-1", "alpha.pptx"),
            _DummyFileRecord("file-2", "beta.pptx"),
        ]
        self.sessions: dict[str, list[tuple[str, str]]] = {
            "conv-1": [("hello", "world")]
        }
        self.user_id = "default"
        self.source_ids: list[str] = ["file-1"]
        self.indexed_paths: list[str] = []
        self.file_index = SimpleNamespace(
            list_source_ids=lambda _user_id: list(self.source_ids)
        )
        self.requests = []

    def resolve_file_refs(self, refs: list[str]) -> list[_DummyFileRecord]:
        output = []
        for ref in refs:
            for record in self.files:
                if ref in {record.file_id, record.name}:
                    output.append(record)
                    break
        return output

    def load_session(self, conversation_id: str):
        messages = self.sessions.get(conversation_id)
        if messages is None:
            return None
        return SimpleNamespace(
            conversation_id=conversation_id,
            graph_source_ids=["file-1"],
            messages=list(messages),
        )

    def index_paths(self, paths: list[str], reindex: bool = False):
        self.indexed_paths.extend(paths)
        self.source_ids.append("file-note-1")
        return _DummyIndexResult(
            successes=[
                {
                    "file_path": paths[0],
                    "file_name": Path(paths[0]).name,
                    "status": "success",
                }
            ]
        )

    def run_turn(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            conversation_id=request.conversation_id,
            artifact={"type": request.artifact_type, "multiple_choice": []},
        )


class _DummyNotebookService:
    def __init__(self, source_dir: str | Path | None = None):
        self.source_dir = Path(source_dir) if source_dir is not None else None
        self.notebooks: dict[str, dict[str, Any]] = {
            "conv-1": {
                "selected_source_ids": ["file-1"],
                "notes": [],
                "artifacts": [],
            }
        }

    def get_notebook(self, conversation_id: str) -> dict[str, Any]:
        return self.notebooks[conversation_id]

    def list_artifacts(self, data_source: dict[str, Any]) -> list[dict[str, Any]]:
        return list(data_source.get("artifacts", []))

    def get_artifact(
        self,
        data_source: dict[str, Any],
        artifact_id: str,
    ) -> dict[str, Any] | None:
        for artifact in data_source.get("artifacts", []):
            if artifact.get("artifact_id") == artifact_id:
                return dict(artifact)
        return None

    def add_note_to_conversation(
        self,
        conversation_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        note = {
            "note_id": kwargs.get("note_id") or "note-1",
            "title": kwargs["title"],
            "text": kwargs["text"],
            "source": "manual",
            "citation_refs": [],
            "created_at": "2026-05-31T12:00:00+00:00",
            "updated_at": "2026-05-31T12:00:00+00:00",
        }
        notes = cast(list[dict[str, Any]], self.notebooks[conversation_id]["notes"])
        notes.append(note)
        return note

    def save_answer_note_to_conversation(
        self,
        conversation_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        note = {
            "note_id": kwargs.get("note_id") or "answer-1",
            "title": kwargs["title"],
            "text": kwargs["answer"],
            "source": "answer",
            "citation_refs": [],
            "created_at": "2026-05-31T12:01:00+00:00",
            "updated_at": "2026-05-31T12:01:00+00:00",
        }
        notes = cast(list[dict[str, Any]], self.notebooks[conversation_id]["notes"])
        notes.append(note)
        return note

    def select_conversation_sources(
        self,
        conversation_id: str,
        source_ids: list[str],
    ) -> list[str]:
        selected = list(source_ids)
        self.notebooks[conversation_id]["selected_source_ids"] = selected
        return selected

    def materialize_note_source(
        self,
        conversation_id: str,
        note: dict[str, Any],
        root_dir: str | Path | None = None,
    ) -> str:
        source_root = self.source_dir or Path(root_dir or ".")
        source_path = source_root / conversation_id / f"mara-note-{note['note_id']}.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(str(note["text"]), encoding="utf-8")
        return str(source_path)

    def record_note_indexed_source_to_conversation(
        self,
        conversation_id: str,
        note_id: str,
        *,
        source_ids: list[str],
        source_path: str,
    ) -> dict[str, Any]:
        notebook = self.notebooks[conversation_id]
        selected_source_ids = cast(list[str], notebook["selected_source_ids"])
        notebook["selected_source_ids"] = [
            *selected_source_ids,
            *source_ids,
        ]
        notes = cast(list[dict[str, Any]], notebook["notes"])
        note = next(item for item in notes if item["note_id"] == note_id)
        note["indexed_source_ids"] = list(source_ids)
        note["indexed_source_path"] = source_path
        return note

    def build_source_guides(self, records):
        return [
            {
                "source_id": record.file_id,
                "name": record.name,
                "summary": f"{record.name} is an indexed pdf source.",
                "key_topics": [Path(record.name).stem.split()[0]],
                "suggested_questions": [
                    f"What are the key points in {record.name}?",
                ],
                "metadata": {"tokens": record.tokens},
            }
            for record in records
        ]

    def save_artifact_to_conversation(
        self,
        conversation_id: str,
        *,
        artifact_type: str,
        payload: Any,
    ) -> dict[str, Any]:
        artifact = {
            "artifact_id": "artifact-1",
            "type": artifact_type,
            "payload": payload,
            "created_at": "2026-05-31T12:06:00+00:00",
        }
        artifacts = cast(
            list[dict[str, Any]],
            self.notebooks[conversation_id]["artifacts"],
        )
        artifacts.append(artifact)
        return artifact


def _extract_json_payload(raw_output: str):
    lines = [line for line in str(raw_output or "").splitlines() if line.strip()]
    decoder = json.JSONDecoder()
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            continue
        payload = "\n".join(lines[index:])
        try:
            parsed, _offset = decoder.raw_decode(payload)
        except json.JSONDecodeError:
            continue
        return parsed
    raise AssertionError(f"expected JSON payload, got:\n{raw_output}")


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
    assert _extract_json_payload(result.output) == {
        "artifact_id": "artifact-1",
        "type": "quiz",
        "payload": {"type": "quiz", "multiple_choice": []},
        "created_at": "2026-05-31T12:06:00+00:00",
    }
    assert service.notebooks["conv-1"]["artifacts"][0]["type"] == "quiz"
