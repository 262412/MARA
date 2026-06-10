import json
from types import SimpleNamespace

from click.testing import CliRunner
from slide_cli.docqa_cli import docqa


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
    def __init__(
        self,
        conversation_id: str,
        active_file_name: str = "alpha.pptx",
        page_number: int | None = 3,
    ):
        self.conversation_id = conversation_id
        self.answer = "dummy answer"
        self.references_text = "dummy evidence"
        self.active_file_name = active_file_name
        self.page_number = page_number
        self.can_apply = False
        self.route_decision = {"route": "hybrid"}
        self.retrieve_decision = {"status": "good"}
        self.verify_decision = {"status": "supported", "action": "generate"}
        self.evidence_bundle = {
            "items": [{"modality": "text"}, {"modality": "page_image"}]
        }

    def as_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "answer": self.answer,
            "references_text": self.references_text,
            "active_file_name": self.active_file_name,
            "page_number": self.page_number,
            "route_decision": self.route_decision,
            "retrieve_decision": self.retrieve_decision,
            "verify_decision": self.verify_decision,
            "evidence_bundle": self.evidence_bundle,
        }


class _DummyRuntime:
    def __init__(self):
        self.files = [
            _DummyFileRecord("file-1", "alpha.pptx"),
            _DummyFileRecord("file-2", "beta.pptx"),
        ]
        self.sessions = {"conv-1": [("hello", "world")]}
        self.last_request = None

    def list_files(self):
        return list(self.files)

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
        self.sessions.setdefault(conversation_id, []).append(
            (request.prompt, "dummy answer")
        )
        active_file_name = request.active_file_name or "alpha.pptx"
        return _DummyResponse(
            conversation_id=conversation_id,
            active_file_name=active_file_name,
            page_number=request.page_number,
        )

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


def _assert_docqa_ask_request(request):
    assert request is not None
    assert request.prompt == "What is alpha?"
    assert request.conversation_id == "conv-9"
    assert request.selected_file_ids == ["file-1"]
    assert request.active_file_id == "file-1"
    assert request.page_number == 3
    assert request.selected_text == "focus text"
    assert request.graph_context == {"related_file_ids": ["file-1"]}
    assert request.controller_mode == "llm"
    assert request.route_policy == "hybrid"
    assert request.verification_mode == "strict"
    assert request.reasoning_type == "chain"
    assert request.task_type == "study_guide"
    assert request.agent_mode == "thorough"
    assert request.artifact_type == "study_guide"
    assert request.llm == "gpt-4o-mini"
    assert request.visual_retriever_backend == "local_late_interaction"
    assert request.visual_generator_backend == "local_qwen3_vl"
    assert request.use_citation == "inline"
    assert request.language == "zh"
    assert request.use_mindmap is True


def test_docqa_ask_json(monkeypatch, tmp_path):
    runtime = _DummyRuntime()
    graph_context_path = tmp_path / "graph.json"
    graph_context_path.write_text('{"related_file_ids":["file-1"]}', encoding="utf-8")

    monkeypatch.setattr(
        "slide_cli.docqa_cli.create_docqa_runtime",
        lambda: runtime,
    )

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "ask",
            "--prompt",
            "What is alpha?",
            "--conversation",
            "conv-9",
            "--file",
            "alpha.pptx",
            "--active-file",
            "alpha.pptx",
            "--page",
            "3",
            "--selected-text",
            "focus text",
            "--graph-context-file",
            str(graph_context_path),
            "--controller",
            "llm",
            "--route",
            "hybrid",
            "--verify",
            "strict",
            "--reasoning",
            "chain",
            "--task",
            "study_guide",
            "--agent-mode",
            "thorough",
            "--artifact",
            "study_guide",
            "--llm",
            "gpt-4o-mini",
            "--visual-retriever",
            "local_late_interaction",
            "--visual-generator",
            "local_qwen3_vl",
            "--citation",
            "inline",
            "--language",
            "zh",
            "--mindmap",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert payload["conversation_id"] == "conv-9"
    assert payload["answer"] == "dummy answer"
    _assert_docqa_ask_request(runtime.last_request)
    assert payload["route_decision"] == {"route": "hybrid"}
    assert payload["verify_decision"] == {
        "status": "supported",
        "action": "generate",
    }


def test_docqa_ask_passes_planner_model_allowed_routes_and_element_route(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "ask",
            "--prompt",
            "What is alpha?",
            "--route",
            "element",
            "--planner-model",
            "fake-planner",
            "--allowed-route",
            "doc_element",
            "--allowed-route",
            "hybrid",
            "--visual-retriever",
            "local_late_interaction",
            "--visual-generator",
            "local_qwen3_vl",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert runtime.last_request is not None
    assert runtime.last_request.route_policy == "element"
    assert runtime.last_request.planner_model == "fake-planner"
    assert runtime.last_request.allowed_routes == ["doc_element", "hybrid"]
    assert runtime.last_request.visual_retriever_backend == "local_late_interaction"
    assert runtime.last_request.visual_generator_backend == "local_qwen3_vl"


def test_docqa_ask_text_includes_controller_summary(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "ask",
            "--prompt",
            "What is alpha?",
            "--controller",
            "llm",
            "--route",
            "hybrid",
            "--verify",
            "strict",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "dummy answer" in result.output
    assert "Route: Hybrid" in result.output
    assert "Retrieval: good" in result.output
    assert "Verification: supported (generate)" in result.output
    assert "Modalities: text, page_image" in result.output


def test_docqa_ask_rejects_non_object_graph_context(monkeypatch, tmp_path):
    runtime = _DummyRuntime()
    graph_context_path = tmp_path / "graph.json"
    graph_context_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "ask",
            "--prompt",
            "What is alpha?",
            "--graph-context-file",
            str(graph_context_path),
        ],
    )

    assert result.exit_code != 0
    assert "--graph-context-file must contain a JSON object." in result.output


def test_docqa_chat_repl_basic_flow(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr(
        "slide_cli.docqa_cli.create_docqa_runtime",
        lambda: runtime,
    )

    runner = CliRunner()
    result = runner.invoke(
        docqa,
        [
            "chat",
            "--file",
            "alpha.pptx",
            "--controller",
            "llm",
            "--route",
            "graph",
            "--verify",
            "light",
            "--visual-retriever",
            "local_late_interaction",
            "--visual-generator",
            "local_qwen3_vl",
        ],
        input="What is alpha?\n/exit\n",
    )

    assert result.exit_code == 0, result.output
    assert runtime.last_request is not None
    assert runtime.last_request.visual_retriever_backend == "local_late_interaction"
    assert runtime.last_request.visual_generator_backend == "local_qwen3_vl"
    assert "Conversation:" in result.output
    assert "dummy answer" in result.output
    assert runtime.last_request.prompt == "What is alpha?"
    assert runtime.last_request.selected_file_ids == ["file-1"]
    assert runtime.last_request.page_number is None
    assert runtime.last_request.controller_mode == "llm"
    assert runtime.last_request.route_policy == "graph"
    assert runtime.last_request.verification_mode == "light"


def test_docqa_files_and_sessions_listing(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr(
        "slide_cli.docqa_cli.collect_docqa_file_records",
        lambda: [record.as_dict() for record in runtime.list_files()],
    )
    monkeypatch.setattr(
        "slide_cli.docqa_cli.collect_docqa_session_summaries",
        lambda: [summary.as_dict() for summary in runtime.list_sessions()],
    )

    runner = CliRunner()
    files_result = runner.invoke(docqa, ["files"])
    sessions_result = runner.invoke(docqa, ["sessions"])

    assert files_result.exit_code == 0, files_result.output
    assert "alpha.pptx" in files_result.output
    assert sessions_result.exit_code == 0, sessions_result.output
    assert "Conversation 1" in sessions_result.output


def test_docqa_acceptance_command(monkeypatch):
    payload = {
        "status": "pass",
        "user_id": "default",
        "work_dir": "temp/slide-acceptance-demo",
        "results": [
            {"name": "doctor"},
            {"name": "ask"},
            {"name": "platform_install"},
        ],
    }
    monkeypatch.setattr(
        "slide_cli.docqa_cli.run_docqa_acceptance_matrix",
        lambda **kwargs: payload,
    )

    runner = CliRunner()
    result = runner.invoke(docqa, ["acceptance"])
    check_result = runner.invoke(docqa, ["check"])
    json_result = runner.invoke(docqa, ["acceptance", "--json"])

    assert result.exit_code == 0, result.output
    assert "Status: PASS" in result.output
    assert "Checks: 3" in result.output
    assert "Coverage: ask, doctor, platform_install" in result.output
    assert check_result.exit_code == 0, check_result.output
    assert "Status: PASS" in check_result.output

    assert json_result.exit_code == 0, json_result.output
    assert _extract_json_payload(json_result.output)["status"] == "pass"


def test_docqa_doctor_uses_lightweight_payload(monkeypatch):
    payload = {
        "ok": True,
        "app_name": "Kotaemon",
        "default_user_id": "default",
        "index_name": "File Collection",
        "index_id": 1,
        "llm_default": "openai",
        "embedding_default": "openai",
        "file_count": 2,
        "session_count": 3,
        "graph_cache_dir": "D:/tmp/knowledge_graph/conversations",
        "issues": [],
        "warnings": ["Default LLM appears to use placeholder credentials."],
    }

    def _unexpected_runtime():
        raise AssertionError("docqa doctor should not create the full DocQA runtime")

    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", _unexpected_runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_cli.collect_docqa_doctor_payload",
        lambda: payload,
    )

    runner = CliRunner()
    result = runner.invoke(docqa, ["doctor", "--json"])
    text_result = runner.invoke(docqa, ["doctor"])

    assert result.exit_code == 0, result.output
    assert _extract_json_payload(result.output) == payload

    assert text_result.exit_code == 0, text_result.output
    assert "Status: OK" in text_result.output
    assert "Default LLM: openai" in text_result.output
    assert "! Default LLM appears to use placeholder credentials." in text_result.output


def test_docqa_files_use_lightweight_collection(monkeypatch):
    payload = [
        {
            "file_id": "file-1",
            "name": "alpha.pptx",
            "tokens": 10,
            "size": 100,
            "loader": "dummy",
            "path": "D:/tmp/alpha.pptx",
            "date_created": "2026-04-22T12:00:00",
        }
    ]

    def _unexpected_runtime():
        raise AssertionError("docqa files should not create the full DocQA runtime")

    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", _unexpected_runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_cli.collect_docqa_file_records",
        lambda: payload,
    )

    runner = CliRunner()
    result = runner.invoke(docqa, ["files", "--json"])
    text_result = runner.invoke(docqa, ["files"])

    assert result.exit_code == 0, result.output
    assert _extract_json_payload(result.output) == payload
    assert text_result.exit_code == 0, text_result.output
    assert "alpha.pptx" in text_result.output


def test_docqa_sessions_use_lightweight_collection(monkeypatch):
    payload = [
        {
            "conversation_id": "conv-1",
            "name": "Conversation 1",
            "message_count": 2,
            "graph_source_count": 1,
            "origin": "cli",
            "is_public": False,
            "date_created": "2026-04-22T12:00:00",
            "date_updated": "2026-04-22T12:05:00",
        }
    ]

    def _unexpected_runtime():
        raise AssertionError("docqa sessions should not create the full DocQA runtime")

    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", _unexpected_runtime)
    monkeypatch.setattr(
        "slide_cli.docqa_cli.collect_docqa_session_summaries",
        lambda: payload,
    )

    runner = CliRunner()
    result = runner.invoke(docqa, ["sessions", "--json"])
    text_result = runner.invoke(docqa, ["sessions"])

    assert result.exit_code == 0, result.output
    assert _extract_json_payload(result.output) == payload
    assert text_result.exit_code == 0, text_result.output
    assert "Conversation 1" in text_result.output


def test_docqa_ask_help_lists_shared_parameters():
    runner = CliRunner()
    result = runner.invoke(docqa, ["ask", "--help"])

    assert result.exit_code == 0, result.output
    for token in [
        "--prompt",
        "--conversation",
        "--file",
        "--active-file",
        "--page",
        "--scope",
        "--selected-text",
        "--graph-context-file",
        "--reasoning",
        "--task",
        "--agent-mode",
        "--artifact",
        "--llm",
        "--citation",
        "--language",
        "--mindmap",
        "--planner-model",
        "--allowed-route",
        "--visual-retriever",
        "--visual-generator",
        "--json",
    ]:
        assert token in result.output
    assert "Whole-document QA:" in result.output
    assert "Page-level QA:" in result.output
    assert "Text-focused QA:" in result.output


def test_docqa_help_lists_action_navigation():
    runner = CliRunner()
    result = runner.invoke(docqa, ["--help"])

    assert result.exit_code == 0, result.output
    for token in [
        "Action guide:",
        "Inspect indexed files",
        "Delete indexed files",
        "Ask one question",
        "Index documents",
        "Interactive chat",
        "Inspect saved sessions",
        "Resume a conversation",
        "Manage notebook notes",
        "Manage selected sources",
        "Manage generated artifacts",
        "Health check",
        "Maintainer acceptance check",
    ]:
        assert token in result.output
