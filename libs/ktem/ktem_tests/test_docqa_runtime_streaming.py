import threading
from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa import _runtime_turn as turn_module
from ktem.docqa.runtime import DocQARuntime
from ktem.docqa.terminal_session_state import terminal_semantic_commit_for_message

from kotaemon.base import Document


class _StreamingMaraPipeline:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    def stream(self, _message, _conv_id, _history):
        yield Document(
            channel="debug",
            content={
                "mara_channel": "agent_trace",
                "payload": {"event": "route", "modality": "text"},
            },
        )
        yield Document(channel="chat", content="grounded ")
        yield Document(
            channel="debug",
            content={
                "mara_channel": "evidence_metadata",
                "payload": {"modalities": {"text": 1}},
            },
        )
        yield Document(channel="chat", content="answer")
        yield Document(
            channel="info",
            content="Grounded answer evidence: grounded answer.",
        )


class _StreamingMaraReasoning:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    @staticmethod
    def get_pipeline(_settings, _state, _retrievers):
        return _StreamingMaraPipeline()


class _LateAnswerLabelPipeline:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    def stream(self, _message, _conv_id, _history):
        yield Document(
            channel="chat",
            content=(
                "The document is a project proposal for MARA, a local-first "
                "document question-answering workbench.\n\n"
                "| Item | Summary |\n"
                "| --- | --- |\n"
                "| Controller | Selects the answer route based on the query. |"
            ),
        )
        yield Document(channel="chat", content="\n\nAnswer: Short answer.")


class _LateAnswerLabelReasoning:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    @staticmethod
    def get_pipeline(_settings, _state, _retrievers):
        return _LateAnswerLabelPipeline()


def _make_runtime():
    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._resolve_user_id = lambda user_id=None: "user-1"
    runtime.load_settings = lambda user_id=None: {"reasoning.use": "mara"}
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    runtime._web_search_cls = None
    runtime.file_index = None
    runtime._preview = SimpleNamespace(
        resolve_file_name=lambda _file_id: "alpha.pdf",
        resolve_file_path=lambda _file_id: "",
    )
    runtime.knowledge_graph = None
    session_info = runtime_module.DocQASession(
        conversation_id="conv-1",
        name="Conversation",
        user_id="user-1",
        is_public=False,
        data_source={},
        messages=[],
        retrieval_messages=[],
        plot_history=[],
        state={"app": {"regen": False}},
        selected_mapping={},
        graph_source_ids=[],
        origin="cli",
        date_created=None,
        date_updated=None,
    )
    runtime.load_session = lambda _conversation_id: None
    runtime.create_session = lambda user_id=None: session_info
    runtime.persisted_states = []

    def persist_conversation_state(**kwargs):
        runtime.persisted_states.append(kwargs["state"])
        return [], []

    runtime.persist_conversation_state = persist_conversation_state
    return runtime


def test_runtime_stream_turn_yields_live_updates_and_final_response(monkeypatch):
    saved_metadata = []
    monkeypatch.setattr(runtime_module, "reasonings", {"mara": _StreamingMaraReasoning})
    monkeypatch.setattr(
        runtime_module._nb,
        "save_captured_artifact",
        lambda _conversation_id, _artifact, **metadata: saved_metadata.append(metadata),
    )

    runtime = _make_runtime()
    updates = list(
        runtime.stream_turn(
            runtime_module.DocQARequest(
                prompt="Summarize this source.",
                verification_mode="light",
            )
        )
    )

    event_updates = [update for update in updates if not update.is_final]
    assert saved_metadata[0]["user_id"] == "user-1"
    assert [update.event["channel"] for update in event_updates] == [
        "debug",
        "chat",
        "debug",
        "chat",
        "info",
    ]
    assert event_updates[1].answer == "grounded"
    assert event_updates[3].answer == "grounded answer"

    final = updates[-1]
    assert final.is_final is True
    assert final.response is not None
    assert final.response.answer == "grounded answer"
    assert (
        final.response.references_html == "Grounded answer evidence: grounded answer."
    )
    expected_reference_evidence: dict[str, Any] = {
        "evidence_id": "citation-refs",
        "source_id": "refs",
        "source_name": "Generated citations",
        "page_label": "",
        "modality": "text",
        "element_id": "",
        "bbox": None,
        "caption": "",
        "text": "Grounded answer evidence: grounded answer.",
        "ocr_text": "",
        "vlm_text": "",
        "source_backrefs": [],
        "evidence_level": "citation",
        "metadata": {"source": "references_html"},
    }
    assert final.response.evidence_metadata == {
        "modalities": {"text": 1},
        "evidence": [expected_reference_evidence],
    }
    assert final.response.retrieve_decision["status"] == "good"
    assert final.response.verify_decision["status"] == "supported"
    [bundle_item] = final.response.evidence_bundle["items"]
    expected_bundle_fields = {
        key: value
        for key, value in expected_reference_evidence.items()
        if key != "source_backrefs"
    }
    assert {
        key: bundle_item[key] for key in expected_bundle_fields
    } == expected_bundle_fields
    assert bundle_item["source_backrefs"] == ["refs#source"]
    assert bundle_item["canonical_id"] == "evidence:refs:citation-refs"
    assert bundle_item["normalized_text_hash"]
    assert final.response.evidence_bundle["metadata"]["schema_version"] == (
        "evidence_bundle.v2"
    )
    assert final.stream_events[-1]["channel"] == "info"
    _assert_persisted_terminal_commit(runtime, final)


def _assert_persisted_terminal_commit(runtime: Any, final: Any) -> None:
    persisted_commit = terminal_semantic_commit_for_message(
        runtime.persisted_states[-1],
        0,
    )
    assert persisted_commit == final.response.engine_terminal_commit


def test_runtime_stream_turn_does_not_replace_substantial_answer_with_late_label(
    monkeypatch,
):
    monkeypatch.setattr(
        runtime_module, "reasonings", {"mara": _LateAnswerLabelReasoning}
    )
    monkeypatch.setattr(
        runtime_module._nb,
        "save_captured_artifact",
        lambda _conversation_id, _artifact, **_metadata: None,
    )

    runtime = _make_runtime()
    updates = list(
        runtime.stream_turn(
            runtime_module.DocQARequest(prompt="Summarize this source.")
        )
    )

    event_updates = [update for update in updates if not update.is_final]
    final = updates[-1]

    assert (
        "local-first document question-answering workbench" in event_updates[-1].answer
    )
    assert "Short answer." not in event_updates[-1].answer
    assert final.response is not None
    assert "local-first document question-answering workbench" in final.response.answer
    assert "Short answer." not in final.response.answer


def test_runtime_stream_turn_cancellation_skips_finalization_and_persistence(
    monkeypatch,
):
    monkeypatch.setattr(runtime_module, "reasonings", {"mara": _StreamingMaraReasoning})
    monkeypatch.setattr(
        runtime_module._nb,
        "save_captured_artifact",
        lambda *_args, **_kwargs: None,
    )
    runtime = _make_runtime()
    runtime._finalize_turn_response = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("A cancelled turn must not be finalized")
    )
    cancelled = threading.Event()
    updates = runtime.stream_turn(
        runtime_module.DocQARequest(prompt="Summarize this source."),
        cancel_event=cancelled,
    )

    first = next(updates)
    cancelled.set()

    assert first.is_final is False
    assert list(updates) == []


def test_finalize_stream_result_ignores_trailing_unclosed_think_block():
    result = turn_module.create_stream_result(
        runtime_module.DocQARequest(prompt="Summarize this source.")
    )
    result.text = (
        "**Answer:**\n"
        "- The document proposes MARA as a local-first document QA workbench.\n"
        "- It combines retrieval, evidence tracking, and answer generation.\n"
        "<think>internal scratch answer: short malformed"
    )

    turn_module.finalize_stream_result(result, "empty")

    assert "short malformed" not in result.text
    assert result.text == (
        "- The document proposes MARA as a local-first document QA workbench.\n"
        "- It combines retrieval, evidence tracking, and answer generation."
    )
