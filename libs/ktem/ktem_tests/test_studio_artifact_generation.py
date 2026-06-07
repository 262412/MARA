from types import SimpleNamespace
from typing import Any

from ktem.db.models import Conversation, engine
from ktem.docqa._runtime_notebook import get_notebook
from ktem.pages.chat.studio_artifact_controls import (
    generate_studio_artifact_panel_update,
    regenerate_latest_studio_artifact_panel_update,
    render_studio_artifact_regenerating_update,
)
from ktem.pages.chat.studio_artifact_generation import (
    build_studio_artifact_prompt,
    run_studio_artifact_regenerate_turn,
    run_studio_artifact_turn,
)
from ktem.pages.chat.studio_artifact_status import save_failed_studio_artifact
from sqlmodel import Session, select


class _Runtime:
    def __init__(self):
        self.request = None

    def run_turn(self, request):
        self.request = request
        return SimpleNamespace(conversation_id=request.conversation_id, artifact={})


class _PanelRuntime(_Runtime):
    def run_turn(self, request):
        self.request = request
        return SimpleNamespace(
            conversation_id="conv-1",
            messages=[("previous", "answer"), (request.prompt, "artifact ready")],
            retrieval_messages=["<details class='evidence'>e</details>"],
            plot_history=[{"plot": "value"}],
            state={"state": "updated"},
            answer="artifact ready",
            references_html="<details class='evidence'>e</details>",
            active_file_id="file-1",
            page_number=2,
            artifact={"type": "quiz"},
            route_decision={"route": "doc_text"},
            retrieve_decision={"status": "good"},
            verify_decision={"status": "supported"},
            evidence_bundle={"items": []},
            graph_source_ids=["file-1"],
        )


class _FailingPanelRuntime(_Runtime):
    def run_turn(self, request):
        self.request = request
        raise RuntimeError("artifact adapter down")


class _PanelPage:
    def __init__(self):
        self.docqa: Any = _PanelRuntime()

    def _build_selected_input_map(self, *selecteds):
        return {7: list(selecteds)}

    def _generate_answer_panel_html(
        self, preserved_history, user_input, ai_response, is_thinking=False
    ):
        assert preserved_history == [("previous", "answer")]
        assert not is_thinking
        return f"answer:{user_input[:10]}:{ai_response}"

    def _render_reasoning_trace_html(
        self,
        question="",
        retrieval_html="",
        answer_html="",
        active_file_id="",
        page_number=None,
        artifact_payload=None,
    ):
        assert artifact_payload == {"type": "quiz"}
        return f"trace:{active_file_id}:{page_number}:{question[:10]}"

    def _render_citations_card_html(self, retrieval_html=""):
        return f"citations:{retrieval_html}"


def test_build_studio_artifact_prompt_includes_user_options():
    prompt = build_studio_artifact_prompt(
        "quiz",
        prompt="Focus on exam prep.",
        output_format="markdown",
        difficulty="hard",
        count=8,
        language="English",
    )

    assert "Focus on exam prep." in prompt
    assert "Preferred format: markdown." in prompt
    assert "Difficulty: hard." in prompt
    assert "Requested item count: 8." in prompt
    assert "Language: English." in prompt


def test_regenerating_update_without_conversation_uses_running_placeholder(
    monkeypatch,
):
    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_controls._latest_notebook_artifact",
        lambda _conversation_id: (_ for _ in ()).throw(AssertionError()),
    )

    html = render_studio_artifact_regenerating_update("")

    assert "studio-artifacts-card--running" in html
    assert "Study Guide" in html


def test_run_studio_artifact_turn_sets_artifact_request_fields():
    runtime = _Runtime()

    run_studio_artifact_turn(
        runtime,
        artifact_type="quiz",
        prompt="Focus on exam prep.",
        output_format="markdown",
        difficulty="hard",
        count=8,
        conversation_id="conv-1",
        chat_history=[("previous", "answer")],
        selected_inputs={7: ["select", ["file-1"], "user-1"]},
        settings={"reasoning.use": "mara"},
        reasoning_type="mara",
        llm_type="gpt-test",
        use_mindmap="default",
        use_citation="default",
        language="English",
        chat_state={"app": {"regen": False}},
        command_state=None,
        user_id="user-1",
        active_file_id="file-1",
        active_file_name="paper.pdf",
        page_number=3,
        qa_scope="document",
        selected_page_text="Selected page evidence.",
        selected_graph_context='{"nodes": []}',
        controller_mode="llm",
        route_policy="auto",
        verification_mode="light",
        planner_model="planner-test",
    )

    request = runtime.request
    assert request is not None
    assert request.artifact_type == "quiz"
    assert request.task_type == "quiz"
    assert request.agent_mode == "auto"
    assert request.prompt.startswith("Focus on exam prep.")
    assert request.conversation_id == "conv-1"
    assert request.selected_inputs == {7: ["select", ["file-1"], "user-1"]}
    assert request.active_file_id == "file-1"
    assert request.page_number == 3
    assert request.qa_scope == "document"
    assert request.selected_text == "Selected page evidence."
    assert request.controller_mode == "llm"
    assert request.route_policy == "auto"
    assert request.verification_mode == "light"
    assert request.planner_model == "planner-test"


def test_run_studio_artifact_turn_uses_selected_notebook_notes(monkeypatch):
    runtime = _Runtime()
    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_generation._notebook_note_records",
        lambda _conversation_id, _note_ids: [
            {
                "note_id": "note-1",
                "title": "Manual note",
                "text": "Use this note as study guide evidence.",
            }
        ],
    )

    run_studio_artifact_turn(
        runtime,
        artifact_type="study_guide",
        prompt="",
        output_format="markdown",
        difficulty="",
        count=0,
        conversation_id="conv-1",
        chat_history=[],
        selected_inputs={},
        settings={},
        reasoning_type="mara",
        llm_type="gpt-test",
        use_mindmap="default",
        use_citation="default",
        language="English",
        chat_state={},
        command_state=None,
        user_id="user-1",
        active_file_id="",
        active_file_name="",
        page_number=1,
        qa_scope="document",
        selected_page_text="",
        selected_graph_context="{}",
        controller_mode="llm",
        route_policy="auto",
        verification_mode="light",
        planner_model="",
        note_ids="note-1",
    )

    request = runtime.request
    assert request is not None
    assert request.note_ids == ["note-1"]
    assert "Notebook notes:" in request.prompt
    assert "Manual note" in request.prompt
    assert "Use this note as study guide evidence." in request.prompt


def test_run_studio_artifact_regenerate_turn_uses_saved_scope_and_prompt():
    runtime = _Runtime()

    run_studio_artifact_regenerate_turn(
        runtime,
        artifact={
            "type": "quiz",
            "prompt": "Original quiz prompt.",
            "source_scope": {
                "mode": "document",
                "source_ids": ["file-1", "file-2"],
                "note_ids": ["note-1"],
            },
        },
        fallback_source_ids=[],
        conversation_id="conv-1",
        chat_history=[],
        selected_inputs={7: ["select", ["current-file"], "user-1"]},
        settings={"reasoning.use": "mara"},
        reasoning_type="mara",
        llm_type="gpt-test",
        use_mindmap="default",
        use_citation="default",
        language="English",
        chat_state={"app": {"regen": False}},
        command_state=None,
        user_id="user-1",
        active_file_id="current-file",
        active_file_name="paper.pdf",
        selected_page_text="",
        selected_graph_context="{}",
        controller_mode="llm",
        route_policy="auto",
        verification_mode="light",
        planner_model="",
    )

    request = runtime.request
    assert request is not None
    assert request.prompt == "Original quiz prompt."
    assert request.artifact_type == "quiz"
    assert request.selected_file_ids == ["file-1", "file-2"]
    assert request.note_ids == ["note-1"]
    assert request.qa_scope == "document"
    assert request.page_number == 1


def test_generate_studio_artifact_panel_update_returns_right_panel_outputs():
    page = _PanelPage()

    result = generate_studio_artifact_panel_update(
        page,
        "quiz",
        "Focus on exam prep.",
        "page",
        "markdown",
        "medium",
        5,
        "conv-1",
        [("previous", "answer")],
        {"reasoning.use": "mara"},
        "mara",
        "gpt-test",
        "default",
        "default",
        "English",
        {"state": "old"},
        None,
        "user-1",
        "file-1",
        "paper.pdf",
        2,
        "Selected page evidence.",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        "",
        "selected-source",
    )

    assert result[0] == "conv-1"
    assert result[1][-1][1] == "artifact ready"
    assert result[2] == ["<details class='evidence'>e</details>"]
    assert result[3] == [{"plot": "value"}]
    assert result[4] == {"state": "updated"}
    assert result[5].startswith("answer:Focus on e")
    assert result[6] == "citations:<details class='evidence'>e</details>"
    assert "trace:file-1:2:Focus on e" in result[7]
    assert "notebook-panel-card" in result[8]
    assert result[9] == ["file-1"]
    assert page.docqa.request is not None
    assert page.docqa.request.selected_inputs == {7: ["selected-source"]}


def test_generate_studio_artifact_panel_update_records_failed_artifact(monkeypatch):
    page = _PanelPage()
    page.docqa = _FailingPanelRuntime()
    saved = []

    def save_failed_artifact(**kwargs):
        saved.append(kwargs)
        return {
            "type": kwargs["artifact_type"],
            "status": "failed",
            "generation": {"error": kwargs["error"]},
        }

    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_status.save_failed_studio_artifact",
        save_failed_artifact,
    )

    result = generate_studio_artifact_panel_update(
        page,
        "quiz",
        "Focus on exam prep.",
        "page",
        "markdown",
        "medium",
        5,
        "conv-1",
        [("previous", "answer")],
        {},
        "mara",
        "gpt-test",
        "default",
        "default",
        "English",
        {"state": "old"},
        None,
        "user-1",
        "file-1",
        "paper.pdf",
        2,
        "Selected page evidence.",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        "",
        "selected-source",
    )

    assert result[0] == "conv-1"
    assert result[1] == [("previous", "answer")]
    assert "studio-artifacts-card--failed" in result[7]
    assert saved[0]["artifact_type"] == "quiz"
    assert saved[0]["active_file_id"] == "file-1"
    assert saved[0]["error"] == "artifact adapter down"


def test_save_failed_studio_artifact_persists_failed_metadata():
    conversation = Conversation(user="user-1")
    conversation.data_source = {"origin": "studio"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id

    try:
        artifact = save_failed_studio_artifact(
            conversation_id=conversation_id,
            artifact_type="quiz",
            prompt="Generate a quiz.",
            qa_scope="page",
            page_number=4,
            active_file_id="file-1",
            note_ids=["note-1"],
            error="artifact adapter down",
        )
        notebook = get_notebook(conversation_id)

        assert artifact["status"] == "failed"
        assert artifact["generation"]["error"] == "artifact adapter down"
        assert artifact["source_scope"]["page"] == 4
        assert (
            notebook["artifacts"][0]["generation"]["error"] == "artifact adapter down"
        )
        assert notebook["artifacts"][0]["source_scope"]["note_ids"] == ["note-1"]
    finally:
        with Session(engine) as session:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if row is not None:
                session.delete(row)
                session.commit()


def test_regenerate_latest_studio_artifact_panel_update_uses_latest_artifact(
    monkeypatch,
):
    page = _PanelPage()
    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_controls._latest_notebook_artifact",
        lambda _conversation_id: {
            "type": "quiz",
            "prompt": "Original quiz prompt.",
            "source_scope": {"mode": "document", "source_ids": ["file-1"]},
        },
    )

    result = regenerate_latest_studio_artifact_panel_update(
        page,
        "conv-1",
        [("previous", "answer")],
        {"reasoning.use": "mara"},
        "mara",
        "gpt-test",
        "default",
        "default",
        "English",
        {"state": "old"},
        None,
        "user-1",
        "current-file",
        "paper.pdf",
        "Selected page evidence.",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        ["file-fallback"],
        "selected-source",
    )

    assert result[0] == "conv-1"
    assert result[1][-1][1] == "artifact ready"
    assert page.docqa.request is not None
    assert page.docqa.request.prompt == "Original quiz prompt."
    assert page.docqa.request.selected_file_ids == ["file-1"]
    assert page.docqa.request.selected_inputs == {7: ["selected-source"]}
