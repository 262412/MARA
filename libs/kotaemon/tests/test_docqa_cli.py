import json
from types import SimpleNamespace

from click.testing import CliRunner

from kotaemon.cli import main


class _DummyFileRecord:
    def __init__(self, file_id: str, name: str):
        self.file_id = file_id
        self.name = name
        self.tokens = 10
        self.size = 100
        self.loader = "dummy"

    def as_dict(self):
        return {
            "file_id": self.file_id,
            "name": self.name,
            "tokens": self.tokens,
            "size": self.size,
            "loader": self.loader,
        }


class _DummySessionSummary:
    def __init__(self, conversation_id: str, name: str):
        self.conversation_id = conversation_id
        self.name = name
        self.message_count = 1
        self.graph_source_count = 1
        self.origin = "cli"

    def as_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "message_count": self.message_count,
            "graph_source_count": self.graph_source_count,
            "origin": self.origin,
        }


class _DummyResponse:
    def __init__(self, conversation_id: str, active_file_name: str = "alpha.pdf"):
        self.conversation_id = conversation_id
        self.answer = "dummy answer"
        self.references_text = "dummy evidence"
        self.active_file_name = active_file_name
        self.page_number = 3

    def as_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "answer": self.answer,
            "references_text": self.references_text,
            "active_file_name": self.active_file_name,
            "page_number": self.page_number,
        }


class _DummyRuntime:
    def __init__(self):
        self.files = [
            _DummyFileRecord("file-1", "alpha.pdf"),
            _DummyFileRecord("file-2", "beta.docx"),
        ]
        self.sessions = {"conv-1": [("hello", "world")]}
        self.last_request = None

    def doctor(self):
        return SimpleNamespace(
            ok=True,
            app_name="Kotaemon",
            default_user_id="default",
            index_name="File Collection",
            index_id=1,
            llm_default="Deepseek",
            embedding_default="google",
            file_count=len(self.files),
            session_count=len(self.sessions),
            graph_cache_dir="graph-cache",
            issues=[],
            as_dict=lambda: {
                "ok": True,
                "index_name": "File Collection",
                "file_count": len(self.files),
            },
        )

    def index_paths(self, paths, reindex=False):
        return SimpleNamespace(
            successes=[{"file_name": path, "status": "success"} for path in paths],
            failures=[],
            debug_messages=[],
            as_dict=lambda: {
                "successes": [{"file_name": path, "status": "success"} for path in paths],
                "failures": [],
                "debug_messages": [],
            },
        )

    def list_files(self):
        return list(self.files)

    def delete_files(self, refs):
        return [record for record in self.files if record.file_id in refs or record.name in refs]

    def list_sessions(self):
        return [_DummySessionSummary("conv-1", "Conversation 1")]

    def resolve_file_refs(self, refs):
        output = []
        for ref in refs:
            for record in self.files:
                if ref in {record.file_id, record.name}:
                    output.append(record)
                    break
        return output

    def run_turn(self, request):
        self.last_request = request
        conversation_id = request.conversation_id or "conv-1"
        self.sessions.setdefault(conversation_id, []).append((request.prompt, "dummy answer"))
        active_file_name = request.active_file_name or "alpha.pdf"
        return _DummyResponse(conversation_id=conversation_id, active_file_name=active_file_name)

    def load_session(self, conversation_id):
        messages = self.sessions.get(conversation_id)
        if messages is None:
            return None
        return SimpleNamespace(
            conversation_id=conversation_id,
            graph_source_ids=["file-1"],
            messages=list(messages),
        )

    def create_session(self):
        conversation_id = f"conv-{len(self.sessions) + 1}"
        self.sessions[conversation_id] = []
        return SimpleNamespace(conversation_id=conversation_id)


def test_docqa_ask_json(monkeypatch, tmp_path):
    runtime = _DummyRuntime()
    graph_context_path = tmp_path / "graph.json"
    graph_context_path.write_text('{"related_file_ids":["file-1"]}', encoding="utf-8")

    monkeypatch.setattr("kotaemon.cli._create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "docqa",
            "ask",
            "--prompt",
            "What is alpha?",
            "--file",
            "alpha.pdf",
            "--active-file",
            "alpha.pdf",
            "--page",
            "3",
            "--selected-text",
            "focus text",
            "--graph-context-file",
            str(graph_context_path),
            "--citation",
            "inline",
            "--language",
            "zh",
            "--mindmap",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["conversation_id"] == "conv-1"
    assert payload["answer"] == "dummy answer"
    assert runtime.last_request.selected_file_ids == ["file-1"]
    assert runtime.last_request.active_file_id == "file-1"
    assert runtime.last_request.page_number == 3
    assert runtime.last_request.selected_text == "focus text"
    assert runtime.last_request.graph_context == {"related_file_ids": ["file-1"]}
    assert runtime.last_request.use_citation == "inline"
    assert runtime.last_request.language == "zh"
    assert runtime.last_request.use_mindmap is True


def test_docqa_chat_repl(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr("kotaemon.cli._create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["docqa", "chat", "--file", "alpha.pdf"],
        input="What is alpha?\n/exit\n",
    )

    assert result.exit_code == 0, result.output
    assert "Conversation:" in result.output
    assert "dummy answer" in result.output
    assert runtime.last_request.prompt == "What is alpha?"
    assert runtime.last_request.selected_file_ids == ["file-1"]


def test_docqa_files_and_sessions(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr("kotaemon.cli._create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    files_result = runner.invoke(main, ["docqa", "files"])
    sessions_result = runner.invoke(main, ["docqa", "sessions"])

    assert files_result.exit_code == 0, files_result.output
    assert "alpha.pdf" in files_result.output
    assert sessions_result.exit_code == 0, sessions_result.output
    assert "Conversation 1" in sessions_result.output


def test_docqa_acceptance_command(monkeypatch):
    payload = {
        "status": "pass",
        "user_id": "default",
        "work_dir": "C:\\temp\\kotaemon-acceptance-demo",
        "results": [
            {"name": "doctor"},
            {"name": "ask"},
            {"name": "platform_install"},
        ],
    }
    monkeypatch.setattr(
        "kotaemon.cli._run_docqa_acceptance_matrix",
        lambda **kwargs: payload,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["docqa", "acceptance"])
    json_result = runner.invoke(main, ["docqa", "acceptance", "--json"])

    assert result.exit_code == 0, result.output
    assert "Status: PASS" in result.output
    assert "Checks: 3" in result.output
    assert "Coverage: ask, doctor, platform_install" in result.output

    assert json_result.exit_code == 0, json_result.output
    assert json.loads(json_result.output)["status"] == "pass"
