from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa import DocQAResponse
from ktem.pages.chat import ChatPage
from ktem.pages.chat.chat_docqa_runtime import build_web_docqa_request
from ktem.pages.chat.chat_docqa_streaming import _typewriter_answer_frames


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


def test_submit_msg_indexes_attached_files_into_selected_scope():
    page = cast(Any, object.__new__(ChatPage))
    indexed_calls = []

    def index_files(files, reindex, settings, user_id):
        indexed_calls.append((files, reindex, settings, user_id))
        return ["file-1"]

    page.first_indexing_file_fn = index_files

    result = page.submit_msg(
        {"text": "Summarize this document", "files": ["/tmp/alpha.pdf"]},
        [],
        1,
        {"reasoning.use": "mara"},
        "conv-1",
        "Conversation",
        [],
        [],
        "",
        "",
        request=SimpleNamespace(),
    )

    assert indexed_calls == [(["/tmp/alpha.pdf"], True, {"reasoning.use": "mara"}, 1)]
    assert result[1] == [("Summarize this document", None)]
    assert result[5] == "select"
    assert result[6]["value"] == ["file-1"]
    assert result[6]["choices"] == [("alpha.pdf", "file-1")]
    assert result[-1] == ["file-1"]


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
            stream_events=[
                {
                    "channel": "debug",
                    "content": {
                        "mara_channel": "agent_trace",
                        "payload": {"event": "route"},
                    },
                }
            ],
            route_decision={"route": "doc_text"},
            retrieve_decision={"status": "good"},
            verify_decision={"status": "supported", "action": "generate"},
            evidence_bundle={"items": [{"modality": "text"}]},
            artifact={"type": "study_guide", "overview": "Evidence summary"},
        )


class _FailingRuntimeDocQA:
    def run_turn(self, request):
        raise ValueError("runtime unavailable")


class _FakeStreamingRuntimeDocQA:
    final_answer = "runtime answer"

    def __init__(self):
        self.request = None

    def stream_turn(self, request):
        self.request = request
        stream_events = [
            {
                "channel": "debug",
                "content": {
                    "mara_channel": "agent_trace",
                    "payload": {"event": "route"},
                },
            }
        ]
        yield SimpleNamespace(
            is_final=False,
            event={"channel": "chat", "content": "runtime "},
            answer="runtime",
            references_html="",
            mindmap_html="",
            plot=None,
            state={"app": {"regen": False}},
            stream_events=[],
            response=None,
        )
        yield SimpleNamespace(
            is_final=False,
            event=stream_events[0],
            answer="runtime",
            references_html="",
            mindmap_html="",
            plot=None,
            state={"app": {"regen": False}},
            stream_events=stream_events,
            response=None,
        )
        yield SimpleNamespace(
            is_final=False,
            event={"channel": "chat", "content": "answer"},
            answer="runtime answer",
            references_html="",
            mindmap_html="",
            plot=None,
            state={"app": {"regen": False}},
            stream_events=stream_events + [{"channel": "chat", "content": "answer"}],
            response=None,
        )
        yield SimpleNamespace(
            is_final=True,
            event={},
            answer=self.final_answer,
            references_html="<details class='evidence'><summary>Source</summary></details>",
            mindmap_html="",
            plot={"graph": "runtime"},
            state={"app": {"regen": False}, "mara": {"state": "ok"}},
            stream_events=stream_events,
            response=_streaming_docqa_response(stream_events, answer=self.final_answer),
        )


class _FakeStreamingRuntimeDocQAWithFinalRewrite(_FakeStreamingRuntimeDocQA):
    final_answer = "short final answer"


def _streaming_docqa_response(stream_events, answer="runtime answer"):
    return DocQAResponse(
        conversation_id="conv-1",
        answer=answer,
        references_html="<details class='evidence'><summary>Source</summary></details>",
        references_text="Source",
        mindmap_html="",
        plot={"graph": "runtime"},
        messages=[("What changed?", answer)],
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
        stream_events=stream_events,
        route_decision={"route": "doc_text"},
        retrieve_decision={"status": "good"},
        verify_decision={"status": "supported", "action": "generate"},
        evidence_bundle={"items": [{"modality": "text"}]},
    )


def test_chat_fn_runs_web_turn_through_docqa_runtime():
    page = cast(Any, object.__new__(ChatPage))
    fake_docqa = _FakeRuntimeDocQA()
    page.docqa = fake_docqa
    page._build_selected_input_map = lambda *selecteds: {9: ["select", ["file-1"], 1]}
    page._json_to_plot = lambda value: {"plot": value}
    page._generate_answer_panel_html = (
        lambda _history, _question, answer, is_thinking=False, reasoning_html="": (
            f"thinking:{is_thinking};answer:{answer};reasoning:{reasoning_html}"
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
            SimpleNamespace(session_hash="session-1"),
            SimpleNamespace(),
        )
    )

    assert len(outputs) == 2
    assert "answer-reasoning-block--streaming" in outputs[0][5]
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
    assert "answer-reasoning-block" in final[5]
    assert "answer-reasoning-block--streaming" not in final[5]
    assert "citations:" in final[6]
    assert "Document" in final[7]
    assert "supported" in final[7]


def test_chat_fn_value_error_yields_empty_answer_panel():
    page = cast(Any, object.__new__(ChatPage))
    page.docqa = _FailingRuntimeDocQA()
    page._build_selected_input_map = lambda *selecteds: {9: ["select", ["file-1"], 1]}
    page._json_to_plot = lambda value: {"plot": value}
    page._generate_answer_panel_html = (
        lambda _history, _question, answer, is_thinking=False, reasoning_html="": (
            f"thinking:{is_thinking};answer:{answer};reasoning:{reasoning_html}"
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
            SimpleNamespace(session_hash="session-1"),
            SimpleNamespace(),
        )
    )

    assert len(outputs) == 2
    final = outputs[-1]
    assert final[0] == [("What changed?", "(Sorry, I don't know)")]
    assert final[3] == {"graph": "state"}
    assert "thinking:False" in final[5]
    assert "answer:(Sorry, I don't know)" in final[5]


def test_chat_fn_streams_docqa_events_into_answer_panel():
    page = cast(Any, object.__new__(ChatPage))
    fake_docqa = _FakeStreamingRuntimeDocQA()
    page.docqa = fake_docqa
    page._build_selected_input_map = lambda *selecteds: {9: ["select", ["file-1"], 1]}
    page._json_to_plot = lambda value: {"plot": value}
    page._generate_answer_panel_html = (
        lambda _history, _question, answer, is_thinking=False, reasoning_html="": (
            f"thinking:{is_thinking};answer:{answer};reasoning:{reasoning_html}"
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
            SimpleNamespace(session_hash="session-1"),
            SimpleNamespace(),
        )
    )

    assert len(outputs) > 5
    assert "live events" not in "".join(str(output[5]) for output in outputs)
    assert any("answer:r" in output[5] for output in outputs)
    assert any("answer:runtime" in output[5] for output in outputs)
    assert any("answer:runtime a" in output[5] for output in outputs)
    assert any("answer:runtime answer" in output[5] for output in outputs)
    assert "answer-reasoning-block--streaming" in outputs[1][5]
    assert "answer-reasoning-block--streaming" in outputs[2][5]
    assert "answer-reasoning-block--streaming" not in outputs[-1][5]
    assert fake_docqa.request is not None
    assert fake_docqa.request.prompt == "What changed?"


def test_chat_fn_final_output_preserves_last_streamed_answer_frame():
    page = cast(Any, object.__new__(ChatPage))
    fake_docqa = _FakeStreamingRuntimeDocQAWithFinalRewrite()
    page.docqa = fake_docqa
    page._build_selected_input_map = lambda *selecteds: {9: ["select", ["file-1"], 1]}
    page._json_to_plot = lambda value: {"plot": value}
    page._generate_answer_panel_html = (
        lambda _history, _question, answer, is_thinking=False, reasoning_html="": (
            f"thinking:{is_thinking};answer:{answer};reasoning:{reasoning_html}"
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
            SimpleNamespace(session_hash="session-1"),
            SimpleNamespace(),
        )
    )

    final = outputs[-1]
    assert any("answer:runtime answer" in str(output[5]) for output in outputs[:-1])
    assert "runtime answer" in final[5]
    assert "short final answer" not in final[5]
    assert final[0] == [("What changed?", "runtime answer")]
    assert final[-1] == [("What changed?", "runtime answer")]


def test_typewriter_display_frames_are_bounded_for_large_answer_delta():
    answer = "x" * 1000

    frames = list(_typewriter_answer_frames("", answer))

    assert frames[-1] == answer
    assert len(frames) <= 128
