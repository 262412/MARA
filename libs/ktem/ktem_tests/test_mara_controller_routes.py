import json

import ktem.reasoning.mara as mara_module
import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import (
    MARA_ABSTAIN_MESSAGE,
    MARA_DIRECT_MESSAGE,
    MARA_PLANNER_ABSTAIN_MESSAGE,
    MaraAgentPipeline,
)
from ktem.reasoning.simple import FullQAPipeline

from kotaemon.base import Document, RetrievedDocument


def _planner_events(events):
    return [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
        and event.content["payload"].get("event") == "planner_output"
    ]


def _fake_answer_stream(_self, _message, _conv_id, _history, **_kwargs):
    yield Document(channel="chat", content="grounded answer")
    return Document(channel="chat", content="grounded answer")


def _visual_docs():
    return [
        RetrievedDocument(
            text="",
            id_="thumb-1",
            metadata={
                "type": "thumbnail",
                "file_id": "file-a",
                "file_name": "hard-negative.pdf",
                "page_label": "1",
                "image_origin": "/tmp/hard-negative.png",
                "late_interaction_tokens": ["policy"],
            },
        ),
        RetrievedDocument(
            text="",
            id_="thumb-5",
            metadata={
                "type": "thumbnail",
                "file_id": "file-b",
                "file_name": "visual.pdf",
                "page_label": "5",
                "image_origin": "/tmp/visual.png",
                "late_interaction_tokens": ["revenue", "chart"],
            },
        ),
    ]


def _visual_page_records():
    return [
        {
            "evidence_id": "page-image:file-a:1",
            "file_id": "file-a",
            "file_name": "hard-negative.pdf",
            "page_label": "1",
            "page_number": 1,
            "page_image_path": "/tmp/hard-negative.png",
            "page_visual_embedding": [1.0, 0.0],
            "late_interaction_tokens": ["policy"],
            "modality": "page_image",
            "text": "Revenue policy text hard negative.",
            "ocr_text": "Revenue policy text hard negative.",
            "source_backrefs": ["file-a#page:1"],
            "metadata": {
                "visual_backend_type": "local_smoke",
                "late_interaction_tokens": ["policy"],
            },
        },
        {
            "evidence_id": "page-image:file-b:5",
            "file_id": "file-b",
            "file_name": "visual.pdf",
            "page_label": "5",
            "page_number": 5,
            "page_image_path": "/tmp/visual.png",
            "page_visual_embedding": [0.0, 1.0],
            "late_interaction_tokens": ["revenue", "chart"],
            "modality": "page_image",
            "text": "Revenue chart visual.",
            "ocr_text": "Revenue chart visual.",
            "source_backrefs": ["file-b#page:5"],
            "metadata": {
                "visual_backend_type": "local_smoke",
                "late_interaction_tokens": ["revenue", "chart"],
            },
        },
    ]


def _visual_answer_stream(self, _message, _conv_id, _history, **_kwargs):
    self._mara_last_docs = _visual_docs()
    yield Document(channel="chat", content="visual answer")
    return Document(channel="chat", content="visual answer")


def _fail_if_text_rag_runs(route_name: str):
    def fail(_self, _message, _conv_id, _history, **_kwargs):
        raise AssertionError(f"{route_name} route should not call text RAG")
        yield

    return fail


def test_mara_evidence_metadata_includes_multimodal_index_records():
    docs = [
        RetrievedDocument(
            text="",
            id_="thumb-4",
            metadata={
                "type": "thumbnail",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "image_origin": "/tmp/page-4.png",
            },
        ),
        RetrievedDocument(
            text="Revenue table text.",
            id_="table-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "thumbnail_doc_id": "thumb-4",
                "element_id": "table-4",
                "element_type": "table",
                "bbox": [1, 2, 3, 4],
                "caption": "Revenue",
            },
        ),
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["table"]},
    )

    assert metadata["page_image_index"][0]["evidence_id"] == "page-image:file-1:4"
    assert metadata["page_image_index"][0]["metadata"]["image_ref"] == "/tmp/page-4.png"
    assert metadata["element_index"][0]["evidence_id"] == "element:file-1:4:table-4"
    assert metadata["element_index"][0]["bbox"] == [1, 2, 3, 4]


def test_mara_evidence_metadata_applies_local_visual_retriever_scores():
    docs = [
        RetrievedDocument(
            text="",
            id_="thumb-1",
            metadata={
                "type": "thumbnail",
                "file_id": "file-a",
                "file_name": "hard-negative.pdf",
                "page_label": "1",
                "image_origin": "/tmp/hard-negative.png",
                "late_interaction_tokens": ["policy"],
            },
        ),
        RetrievedDocument(
            text="",
            id_="thumb-5",
            metadata={
                "type": "thumbnail",
                "file_id": "file-b",
                "file_name": "visual.pdf",
                "page_label": "5",
                "image_origin": "/tmp/visual.png",
                "late_interaction_tokens": ["revenue", "chart"],
            },
        ),
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["figure"], "question": "What does the revenue chart show?"},
    )

    assert metadata["page_image_index"][0]["evidence_id"] == "page-image:file-b:5"
    assert (
        metadata["visual_retriever_scores"]["page-image:file-b:5"]
        > metadata["visual_retriever_scores"]["page-image:file-a:1"]
    )


def test_mara_stream_uses_structured_planner_callable(monkeypatch):
    def fake_planner(payload):
        assert payload["question"] == "What does the figure show?"
        assert payload["planner_model"] == "fake-planner"
        return json.dumps(
            {
                "route": "visual",
                "reason": "The question asks about page imagery.",
            }
        )

    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = fake_planner
    pipeline.planner_model = "fake-planner"

    events = list(pipeline.stream("What does the figure show?", "conv-1", []))

    planner_event = _planner_events(events)[0]
    assert planner_event["event"] == "planner_output"
    assert planner_event["planner_model"] == "fake-planner"
    decision = planner_event["decision"]
    assert decision["route"] == "doc_page_image"
    assert decision["evidence_types"] == ["page_image"]
    assert decision["verify"] is True
    assert decision["planner_route"] == "doc_page_image"
    assert decision["scored_route"] == "doc_page_image"
    assert decision["route_selection_policy"] == "cost_aware_initial"
    assert decision["routing_features"]["visual_intent"] is True


def test_mara_stream_falls_back_when_structured_planner_is_invalid(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: "not json"

    events = list(pipeline.stream("What changed?", "conv-1", []))

    decision = _planner_events(events)[0]["decision"]
    assert decision["route"] == "doc_text"
    assert decision["evidence_types"] == ["text"]
    assert decision["verify"] is True
    assert decision["planner_route"] == "doc_text"
    assert decision["scored_route"] == "doc_text"
    assert decision["route_selection_policy"] == "cost_aware_initial"


def test_mara_stream_passes_question_to_visual_retriever(monkeypatch):
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "visual"
    pipeline.page_image_index_records = _visual_page_records()

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))
    evidence_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "evidence_metadata"
    ]

    metadata = evidence_events[0]
    assert metadata["page_image_index"][0]["evidence_id"] == "page-image:file-b:5"
    assert (
        metadata["visual_retriever_scores"]["page-image:file-b:5"]
        > metadata["visual_retriever_scores"]["page-image:file-a:1"]
    )


def test_mara_direct_route_returns_without_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Direct"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "direct", "reason": "Greeting does not require retrieval."}
    )

    events = list(pipeline.stream("hello", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_DIRECT_MESSAGE
    ]


def test_mara_route_policy_direct_overrides_planner_before_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Direct"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "direct"
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "doc", "reason": "Planner would retrieve."}
    )

    events = list(pipeline.stream("hello", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_DIRECT_MESSAGE
    ]


def test_mara_controller_off_ignores_planner_and_uses_route_policy(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    captured = {}
    original_execute = mara_module.execute_controller_turn

    def capture_execute(request, **kwargs):
        result = original_execute(request, **kwargs)
        captured["request"] = request
        captured["result"] = result
        return result

    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.controller_mode = "off"
    pipeline.route_policy = "auto"
    pipeline.verification_mode = "off"
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "direct", "reason": "Planner would skip retrieval."}
    )
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (
            [
                RetrievedDocument(
                    text="Document evidence.",
                    id_="doc-1",
                    metadata={"file_id": "file-1", "page_label": "1"},
                )
            ],
            [],
        ),
    )
    monkeypatch.setattr(mara_module, "execute_controller_turn", capture_execute)

    events = list(pipeline.stream("What changed?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "grounded answer"
    ]
    assert captured["request"].controller_mode == "off"
    assert captured["result"].controller_decision.legacy_route == "doc_text"


def test_mara_text_route_adds_answer_format_requirements(monkeypatch):
    captured = {}

    def capture_stream(_self, message, _conv_id, _history, **_kwargs):
        captured["message"] = message
        yield Document(channel="chat", content="grounded answer")
        return Document(channel="chat", content="grounded answer")

    monkeypatch.setattr(FullQAPipeline, "stream", capture_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "doc"
    pipeline.verification_mode = "off"
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (
            [
                RetrievedDocument(
                    text="Attention uses Q, K, V matrices.",
                    id_="doc-1",
                    metadata={"file_id": "file-1", "page_label": "7"},
                )
            ],
            [],
        ),
    )

    list(
        pipeline.stream(
            "Tell me what formulas are on this page and summarize with a table.",
            "conv-1",
            [],
        )
    )

    assert captured["message"].startswith("Tell me what formulas")
    assert "Return the final answer as Markdown" in captured["message"]
    assert "Put a blank line between paragraphs" in captured["message"]
    assert "Markdown table" in captured["message"]
    assert "$...$" in captured["message"]
    assert "```" in captured["message"]


def test_mara_abstain_route_returns_without_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Abstain"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "abstain", "reason": "No selected source."}
    )

    events = list(pipeline.stream("What is in the source?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_PLANNER_ABSTAIN_MESSAGE
    ]


def test_mara_text_route_abstains_on_poor_retrieval_before_generator(monkeypatch):
    monkeypatch.setattr(
        FullQAPipeline, "stream", _fail_if_text_rag_runs("Poor retrieval")
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "doc", "reason": "Needs document text."}
    )
    monkeypatch.setattr(pipeline, "retrieve", lambda _message, _history: ([], []))

    events = list(pipeline.stream("What does the source say?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_ABSTAIN_MESSAGE
    ]
    trace_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
    ]
    assert any(
        event.get("event") == "guardrail" and event.get("action") == "abstain"
        for event in trace_events
    )


def test_mara_page_image_route_uses_page_image_index_without_text_retrieval(
    monkeypatch,
):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Visual"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "visual", "reason": "Needs page image evidence."}
    )
    pipeline.page_image_index_records = [
        {
            "evidence_id": "page-image:file-b:5",
            "file_id": "file-b",
            "file_name": "visual.pdf",
            "page_label": "5",
            "page_number": 5,
            "page_image_path": "data:image/png;base64,page-5",
            "page_visual_embedding": [0.0, 1.0],
            "late_interaction_tokens": ["revenue", "chart"],
            "modality": "page_image",
            "text": "Revenue chart visual.",
            "ocr_text": "Revenue chart visual.",
            "source_backrefs": ["file-b#page:5"],
            "metadata": {
                "visual_backend_type": "local_smoke",
                "late_interaction_tokens": ["revenue", "chart"],
            },
        }
    ]
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (_ for _ in ()).throw(
            AssertionError("visual route must not use text retrieval")
        ),
    )

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))

    chat_messages = [event.content for event in events if event.channel == "chat"]
    assert len(chat_messages) == 1
    assert "visual page evidence" in chat_messages[0]
    evidence_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "evidence_metadata"
    ]
    assert evidence_events[0]["page_image_index"][0]["evidence_id"] == (
        "page-image:file-b:5"
    )


def test_mara_page_image_route_builds_local_index_from_selected_files(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Visual"))
    monkeypatch.setattr(
        route_retrieval,
        "build_local_page_image_records",
        lambda records, page_numbers=None: _visual_page_records(),
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "visual"
    pipeline.active_file_id = "file-b"
    pipeline.page_number = 5
    pipeline.selected_file_records = [
        {
            "file_id": "file-b",
            "file_name": "visual.pdf",
            "path": "/tmp/visual.pdf",
        }
    ]
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (_ for _ in ()).throw(
            AssertionError("visual route must not use text retrieval")
        ),
    )

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))

    evidence_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "evidence_metadata"
    ]
    assert evidence_events[0]["page_image_index"][0]["evidence_id"] == (
        "page-image:file-b:5"
    )


def test_mara_page_image_route_without_vlm_returns_evidence_only_answer(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Visual"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "visual", "reason": "Needs page image evidence."}
    )
    pipeline.page_image_index_records = _visual_page_records()

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))

    chat_messages = [event.content for event in events if event.channel == "chat"]
    assert len(chat_messages) == 1
    assert "visual page evidence" in chat_messages[0]
    evidence_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "evidence_metadata"
    ]
    assert evidence_events[0]["generation_backend"] == "evidence_only_without_vlm"


def test_mara_strict_verifier_abstains_unsupported_generated_answer(monkeypatch):
    def unsupported_stream(_self, _message, _conv_id, _history, **_kwargs):
        yield Document(channel="chat", content="Profit declined sharply.")
        return Document(channel="chat", content="Profit declined sharply.")

    monkeypatch.setattr(FullQAPipeline, "stream", unsupported_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.verification_mode = "strict"
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "doc", "reason": "Needs document text."}
    )
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda _message, _history: (
            [
                RetrievedDocument(
                    text="Revenue increased in 2026.",
                    id_="doc-1",
                    metadata={"file_id": "file-1", "page_label": "2"},
                )
            ],
            [],
        ),
    )

    events = list(pipeline.stream("What happened to revenue?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_ABSTAIN_MESSAGE
    ]
    trace_events = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
    ]
    assert any(
        event.get("event") == "verifier" and event.get("status") == "unsupported"
        for event in trace_events
    )
