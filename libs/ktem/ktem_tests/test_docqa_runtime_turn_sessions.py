from ktem.docqa import _runtime_sessions, _runtime_turn
from ktem.docqa._runtime_models import _PreparedPipeline
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.docqa.runtime import DocQARequest

from kotaemon.base import Document


def test_runtime_turn_stream_capture_collects_channels_and_mara_payloads():
    prepared = _PreparedPipeline(
        pipeline=_StreamingPipeline(),
        reasoning_state={"pipeline": {"step": "done"}},
        selected_file_ids=[],
        active_file_id="",
        active_file_name="",
        qa_scope="document",
        page_number=None,
        selected_text="",
        graph_context={},
        settings={},
        reasoning_id="mara",
    )
    request = DocQARequest(prompt="Question", state={"app": {}})

    result = _runtime_turn.collect_stream_result(
        prepared,
        request,
        conversation_id="conv-1",
        history=[],
        empty_message="empty",
    )

    assert result.text == "answer"
    assert result.refs == "refs<svg class='markmap'></svg>"
    assert result.mindmap_html == "<svg class='markmap'></svg>"
    assert result.plot == {"nodes": []}
    assert result.state["mara"] == {"step": "done"}
    assert result.stream_events[-1]["channel"] == "plot"
    assert result.capture.agent_trace == [{"event": "route"}]


def test_runtime_turn_response_text_excludes_rendered_thought_details():
    prepared = _PreparedPipeline(
        pipeline=_RenderedThoughtPipeline(),
        reasoning_state={"pipeline": {"step": "done"}},
        selected_file_ids=[],
        active_file_id="",
        active_file_name="",
        qa_scope="document",
        page_number=None,
        selected_text="",
        graph_context={},
        settings={},
        reasoning_id="mara",
    )
    request = DocQARequest(prompt="Question", state={"app": {}})

    result = _runtime_turn.collect_stream_result(
        prepared,
        request,
        conversation_id="conv-1",
        history=[],
        empty_message="empty",
    )

    assert result.text == "Revenue increased in 2026."
    assert "<details" not in result.text
    assert "Thought" not in result.text


def test_runtime_sessions_prepares_append_and_regen_histories():
    appended = _runtime_sessions.prepare_conversation_histories(
        retrieval_message="refs-2",
        plot_data={"plot": 2},
        retrieval_history=["refs-1"],
        plot_history=[{"plot": 1}],
        state={"app": {"regen": False}},
    )
    regenerated = _runtime_sessions.prepare_conversation_histories(
        retrieval_message="refs-new",
        plot_data={"plot": "new"},
        retrieval_history=["refs-old"],
        plot_history=[{"plot": "old"}],
        state={"app": {"regen": True}},
    )

    assert appended.retrieval_history == ["refs-1", "refs-2"]
    assert appended.plot_history == [{"plot": 1}, {"plot": 2}]
    assert appended.state["app"]["regen"] is False
    assert regenerated.retrieval_history == ["refs-new"]
    assert regenerated.plot_history == [{"plot": "new"}]
    assert regenerated.state["app"]["regen"] is False


def test_runtime_sessions_builds_owner_data_source_preserving_notebook_state():
    data_source = {
        "selected": {"9": ["select", ["old"], "user-1"]},
        "likes": [{"message": 1}],
        "chat_suggestions": ["next"],
        "origin": "cli",
        NOTEBOOK_KEY: {"notes": [{"note_id": "note-1", "text": "note text"}]},
    }

    updated = _runtime_sessions.build_conversation_data_source(
        data_source=data_source,
        selected_mapping={"9": ["select", ["file-1"], "user-1"]},
        is_owner=True,
        messages=[("question", "answer")],
        retrieval_history=["refs"],
        plot_history=[{"plot": 1}],
        state={"app": {"regen": False}},
        graph_source_ids=["file-1"],
        origin="web",
    )

    assert updated["selected"] == {"9": ["select", ["file-1"], "user-1"]}
    assert updated["likes"] == [{"message": 1}]
    assert updated["chat_suggestions"] == ["next"]
    assert updated["origin"] == "web"
    assert updated[NOTEBOOK_KEY]["notes"][0]["note_id"] == "note-1"


def test_runtime_sessions_preserves_selected_mapping_for_non_owner():
    updated = _runtime_sessions.build_conversation_data_source(
        data_source={"selected": {"9": ["select", ["old"], "owner"]}},
        selected_mapping={"9": ["select", ["new"], "other"]},
        is_owner=False,
        messages=[],
        retrieval_history=[],
        plot_history=[],
        state={"app": {"regen": False}},
        graph_source_ids=[],
        origin=None,
    )

    assert updated["selected"] == {"9": ["select", ["old"], "owner"]}


class _StreamingPipeline:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    def stream(self, _prompt, _conversation_id, _history):
        yield Document(
            channel="debug",
            content={
                "mara_channel": "agent_trace",
                "payload": {"event": "route"},
            },
        )
        yield Document(channel="chat", content="answer")
        yield Document(channel="info", content="refs")
        yield Document(channel="info", content="<svg class='markmap'></svg>")
        yield Document(channel="plot", content={"nodes": []})


class _RenderedThoughtPipeline:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    def stream(self, _prompt, _conversation_id, _history):
        yield Document(channel="chat", content="raw <think>draft</think>")
        yield Document(channel="chat", content=None)
        yield Document(
            channel="chat",
            content=(
                "<details><summary><span style='color:grey'>Thought</span>"
                "</summary><blockquote>draft</blockquote></details>\n\n"
                "Final answer: Revenue increased in 2026."
            ),
        )
