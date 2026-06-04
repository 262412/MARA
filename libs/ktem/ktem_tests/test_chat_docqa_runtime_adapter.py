from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa import DocQAResponse
from ktem.pages.chat import ChatPage
from ktem.pages.chat.chat_docqa_runtime import build_web_docqa_request


def test_web_docqa_request_preserves_research_controls():
    request = build_web_docqa_request(
        prompt="What does the table show?",
        controller_mode="off",
        route_policy="element",
        verification_mode="strict",
        planner_model="fake-planner",
        allowed_routes=["doc_element", "hybrid"],
    )

    assert request.controller_mode == "off"
    assert request.route_policy == "element"
    assert request.verification_mode == "strict"
    assert request.planner_model == "fake-planner"
    assert request.allowed_routes == ["doc_element", "hybrid"]


class _FakeDocQA:
    def __init__(self):
        self.request = None

    def create_pipeline(self, request):
        self.request = request
        return "pipeline", {"pipeline": {"state": "ok"}}


def test_chat_create_pipeline_builds_controller_enabled_docqa_request():
    page = cast(Any, object.__new__(ChatPage))
    fake_docqa = _FakeDocQA()
    page.docqa = fake_docqa
    page._build_selected_input_map = lambda *selecteds: {9: ["file-1"]}

    pipeline, reasoning_state = page.create_pipeline(
        {"reasoning.use": "mara"},
        "mara",
        "gpt-4o-mini",
        True,
        "inline",
        "en",
        {"app": {"regen": False}},
        None,
        1,
        "file-1",
        "alpha.pdf",
        3,
        "page",
        "selected text",
        '{"related_file_ids": ["file-1"]}',
        "off",
        "element",
        "strict",
        "fake-planner",
        SimpleNamespace(),
    )

    assert pipeline == "pipeline"
    assert reasoning_state == {"pipeline": {"state": "ok"}}
    request = fake_docqa.request
    assert request is not None
    assert request.controller_mode == "off"
    assert request.route_policy == "element"
    assert request.verification_mode == "strict"
    assert request.planner_model == "fake-planner"
    assert request.origin == "web"
    assert request.selected_inputs == {9: ["file-1"]}


class _FakeRuntimeDocQA:
    def __init__(self):
        self.request = None

    def run_turn(self, request):
        self.request = request
        return DocQAResponse(
            conversation_id="conv-1",
            answer="runtime answer",
            references_html="<details class='evidence'><summary>Source</summary></details>",
            references_text="Source",
            mindmap_html="<div class='markmap'></div>",
            plot={"graph": "runtime"},
            messages=[("What changed?", "runtime answer")],
            retrieval_messages=["refs"],
            plot_history=[],
            state={"app": {"regen": False}, "mara": {"state": "ok"}},
            selected_file_ids=["file-1"],
            selected_mapping={},
            graph_source_ids=["file-1"],
            active_file_id="file-1",
            active_file_name="alpha.pdf",
            qa_scope="page",
            page_number=3,
            selected_text="selected text",
            graph_context={"related_file_ids": ["file-1"]},
            reasoning_id="mara",
            settings={"reasoning.use": "mara"},
            stream_events=[],
            route_decision={"route": "doc_text"},
            retrieve_decision={"status": "good"},
            verify_decision={"status": "supported", "action": "generate"},
            evidence_bundle={"items": [{"modality": "text"}]},
            artifact={"type": "study_guide", "overview": "Evidence summary"},
        )


def test_chat_fn_runs_web_turn_through_docqa_runtime():
    page = cast(Any, object.__new__(ChatPage))
    fake_docqa = _FakeRuntimeDocQA()
    page.docqa = fake_docqa
    page._build_selected_input_map = lambda *selecteds: {9: ["select", ["file-1"], 1]}
    page._json_to_plot = lambda value: {"plot": value}
    page._generate_answer_panel_html = (
        lambda _history, _question, answer, is_thinking=False: (
            f"thinking:{is_thinking};answer:{answer}"
        )
    )
    page._render_citations_card_html = lambda refs="": f"citations:{refs}"
    page._render_reasoning_trace_html = (
        lambda question, refs, answer_html, file_id, page_number, artifact=None: (
            f"trace:{question}:{refs}:{file_id}:{page_number}:{artifact}"
        )
    )

    outputs = list(
        page.chat_fn(
            "conv-1",
            [("What changed?", None)],
            {"reasoning.use": "mara"},
            "mara",
            "gpt-4o-mini",
            True,
            "inline",
            "en",
            {"app": {"regen": False}},
            None,
            1,
            "file-1",
            "alpha.pdf",
            3,
            "page",
            "selected text",
            '{"related_file_ids": ["file-1"]}',
            "off",
            "element",
            "strict",
            "fake-planner",
            {"graph": "state"},
            SimpleNamespace(),
            request=SimpleNamespace(session_hash="session-1"),
        )
    )

    assert len(outputs) == 2
    request = fake_docqa.request
    assert request is not None
    assert request.prompt == "What changed?"
    assert request.conversation_id == "conv-1"
    assert request.history == []
    assert request.controller_mode == "off"
    assert request.route_policy == "element"
    assert request.verification_mode == "strict"
    assert request.planner_model == "fake-planner"
    assert request.origin == "web"
    assert request.graph_context == {"related_file_ids": ["file-1"]}
    final = outputs[-1]
    assert len(final) == 14
    assert final[0] == [("What changed?", "runtime answer")]
    assert final[3] == {"graph": "runtime"}
    assert final[4] == {"app": {"regen": False}, "mara": {"state": "ok"}}
    assert "runtime answer" in final[5]
    assert "citations:" in final[6]
    assert "Document" in final[7]
    assert "supported" in final[7]
