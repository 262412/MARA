from types import SimpleNamespace
from typing import cast

from click.testing import CliRunner
from ktem.docqa import DocQARequest
from ktem.docqa.runtime import DocQARuntime
from slide_cli.docqa_cli import _run_docqa_turn, docqa


class _Response:
    conversation_id = "conv-1"
    answer = "ok"
    references_text = ""
    active_file_name = ""
    page_number = None

    def as_dict(self):
        return {"conversation_id": self.conversation_id, "answer": self.answer}


class _RuntimeProbe:
    def __init__(self):
        self.file_index = None
        self.last_request: DocQARequest | None = None
        self.turn_request: DocQARequest | None = None
        self.sessions = {}

    def _resolve_user_id(self, user_id):
        return user_id or "user-1"

    def load_session(self, conversation_id, user_id=None):
        del user_id
        return self.sessions.get(conversation_id)

    def create_session(self, user_id=None):
        session = SimpleNamespace(
            conversation_id="conv-1",
            state={"app": {"regen": False}},
            messages=[],
        )
        self.sessions[session.conversation_id] = session
        return session

    def _resolve_selected_inputs(self, request, session_info):
        return dict(request.selected_inputs or {})

    def load_settings(self, user_id):
        return {"reasoning.use": "mara"}

    def _prepare_pipeline(self, request):
        self.turn_request = request
        return SimpleNamespace(
            pipeline=SimpleNamespace(),
            reasoning_state={},
            selected_file_ids=list(request.selected_file_ids or []),
            active_file_id=request.active_file_id,
            active_file_name=request.active_file_name,
            qa_scope=request.qa_scope,
            page_number=request.page_number,
            selected_text=request.selected_text,
            graph_context=dict(request.graph_context or {}),
            settings=dict(request.settings or {}),
            reasoning_id="mara",
        )

    def run_turn(self, request):
        self.last_request = request
        DocQARuntime._prepare_turn_execution(cast(DocQARuntime, self), request)
        return _Response()


def test_cli_request_reaches_runtime_prepare_turn_execution_with_phase1_fields():
    runtime = _RuntimeProbe()
    page_image_records = [{"evidence_id": "page-image:file-1:3", "page_label": "3"}]

    _run_docqa_turn(
        runtime,
        prompt="/no_think What changed?",
        planner_backend="heuristic_local",
        verification_domain="finance",
        page_image_records=page_image_records,
        max_context_length=4096,
    )

    turn_request = runtime.turn_request
    assert turn_request is not None
    assert turn_request.planner_backend == "heuristic_local"
    assert turn_request.verification_domain == "finance"
    assert turn_request.page_image_records == page_image_records
    assert turn_request.max_context_length == 4096


def test_docqa_ask_and_chat_accept_phase1_options(monkeypatch):
    runtime = _RuntimeProbe()
    monkeypatch.setattr("slide_cli.docqa_cli.create_docqa_runtime", lambda: runtime)
    runner = CliRunner()

    ask_result = runner.invoke(
        docqa,
        [
            "ask",
            "--prompt",
            "/no_think What changed?",
            "--planner-backend",
            "heuristic_local",
            "--verification-domain",
            "finance",
            "--max-context-length",
            "4096",
            "--json",
        ],
    )

    assert ask_result.exit_code == 0, ask_result.output
    ask_request = runtime.last_request
    assert ask_request is not None
    assert ask_request.prompt.startswith("/no_think ")
    assert ask_request.planner_backend == "heuristic_local"
    assert ask_request.verification_domain == "finance"
    assert ask_request.max_context_length == 4096

    chat_result = runner.invoke(
        docqa,
        [
            "chat",
            "--planner-backend",
            "heuristic_local",
            "--verification-domain",
            "finance",
            "--max-context-length",
            "4096",
        ],
        input="/no_think What changed?\n/exit\n",
    )

    assert chat_result.exit_code == 0, chat_result.output
    chat_request = runtime.last_request
    assert chat_request is not None
    assert chat_request.prompt.startswith("/no_think ")
    assert chat_request.planner_backend == "heuristic_local"
    assert chat_request.verification_domain == "finance"
    assert chat_request.max_context_length == 4096
