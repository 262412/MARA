import json

import ktem.reasoning.mara_controller as mara_controller
import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import MARA_PLANNER_ABSTAIN_MESSAGE, MaraAgentPipeline
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


def _fail_if_text_rag_runs(route_name: str):
    def fail(_self, _message, _conv_id, _history, **_kwargs):
        raise AssertionError(f"{route_name} route should not call text RAG")
        yield

    return fail


def _visual_page_records():
    return [
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
        }
    ]


def _element_record():
    return {
        "evidence_id": "element:file-b:5:table-1",
        "file_id": "file-b",
        "file_name": "tables.pdf",
        "page_label": "5",
        "element_id": "table-1",
        "element_type": "table",
        "modality": "table",
        "caption": "Revenue table",
        "text": "Revenue increased in 2026.",
        "source_backrefs": ["file-b#page:5"],
    }


def test_mara_stream_uses_planner_model_when_no_planner_callable(monkeypatch):
    planner_calls = []

    def fake_planner_model(payload, planner_model):
        planner_calls.append((payload, planner_model))
        return json.dumps(
            {
                "route": "visual",
                "reason": "The model selected visual evidence.",
            }
        )

    monkeypatch.setattr(
        mara_controller,
        "_run_planner_model",
        fake_planner_model,
        raising=False,
    )
    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner_model = "fake-planner"

    events = list(pipeline.stream("What does the chart show?", "conv-1", []))

    assert planner_calls[0][1] == "fake-planner"
    assert planner_calls[0][0]["question"] == "What does the chart show?"
    assert _planner_events(events)[0]["decision"]["route"] == "doc_page_image"


def test_mara_planner_model_backend_failure_abstains_with_trace(monkeypatch):
    def unavailable_planner(_payload, _planner_model):
        raise RuntimeError("modelcli backend is not configured")

    monkeypatch.setattr(
        mara_controller,
        "_run_planner_model",
        unavailable_planner,
        raising=False,
    )
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Planner"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner_model = "fake-planner"

    events = list(pipeline.stream("What changed?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_PLANNER_ABSTAIN_MESSAGE
    ]
    decision = _planner_events(events)[0]["decision"]
    assert decision["route"] == "abstain"
    assert decision["planner_error"] == "modelcli backend is not configured"


def test_mara_heuristic_planner_respects_allowed_routes_for_visual_question():
    decision = mara_controller.planner_decision(
        {"task_type": "qa", "modalities": ["figure"], "scope": "page"},
        question="What does the figure show?",
        allowed_routes=["doc_text", "graph_global"],
    )

    assert decision["route"] == "doc_text"
    assert decision["evidence_types"] == ["text"]


def test_mara_stream_exposes_page_image_capability_to_planner(monkeypatch):
    captured = {}

    def fake_execute(
        self,
        message,
        conv_id,
        history,
        understanding,
        planner_payload,
        kwargs,
    ):
        del self, message, conv_id, history, kwargs
        captured["understanding"] = dict(understanding)
        captured["planner_payload"] = dict(planner_payload)
        raise RuntimeError("stop after planner")

    monkeypatch.setattr(
        MaraAgentPipeline,
        "execute_controller_route",
        fake_execute,
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
    pipeline.visual_retriever_backend = "colqwen"

    try:
        list(
            pipeline.stream(
                "What are the key financial metrics and potential risks?",
                "conv-1",
                [],
            )
        )
    except RuntimeError as exc:
        assert str(exc) == "stop after planner"

    assert captured["understanding"]["available_modalities"] == ["page_image"]
    assert captured["planner_payload"]["decision"]["route"] == "doc_text"
    assert captured["planner_payload"]["decision"]["latency_budget_reason"] == (
        "text_route_avoids_visual_latency"
    )


def test_mara_element_route_uses_element_index_without_text_retrieval():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.element_index_records = [_element_record()]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "What does the revenue table show?",
        [],
        {"question": "What does the revenue table show?", "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert (
        metadata["element_index"][0]["evidence_id"] == _element_record()["evidence_id"]
    )
    assert metadata["modality_counts"] == {"table": 1}


def test_mara_text_route_records_bounded_retrieval_attempt_diagnostics():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline._mara_retrieval_attempts = [
        {"attempt": 1, "evidence_count": 1, "retry_reason": ""}
    ]
    docs = [
        RetrievedDocument(
            text="Revenue increased.",
            id_="doc-1",
            metadata={"file_id": "file-1", "page_label": "2"},
        )
    ]
    info = [Document(channel="info", content="<large rendered evidence>")]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "text_rag",
        "What happened to revenue?",
        [],
        {"question": "What happened to revenue?", "modalities": ["text"]},
        text_retrieve=lambda: (docs, info),
        metadata_builder=pipeline.build_evidence_metadata,
    )

    assert metadata["retrieval_attempts"] == [
        {"attempt": 1, "evidence_count": 1, "retry_reason": ""}
    ]
    assert metadata["retrieval_info_count"] == 1
    assert "<large rendered evidence>" not in json.dumps(metadata)


def test_mara_page_image_route_uses_configured_visual_retriever():
    class FakeVisualRetriever:
        name = "fake_visual_retriever"
        backend_type = "unit_test"

        def score(self, _query, record):
            if record["evidence_id"] == "page-image:file-b:6":
                return 42.0
            return 0.1

    pipeline = MaraAgentPipeline(retrievers=[])
    records = _visual_page_records()
    records.append(
        {
            "evidence_id": "page-image:file-b:6",
            "file_id": "file-b",
            "file_name": "visual.pdf",
            "page_label": "6",
            "page_number": 6,
            "page_image_path": "/tmp/other.png",
            "page_visual_embedding": [1.0, 0.0],
            "late_interaction_tokens": ["inventory"],
            "modality": "page_image",
            "text": "Inventory diagram.",
            "ocr_text": "Inventory diagram.",
            "source_backrefs": ["file-b#page:6"],
            "metadata": {"visual_backend_type": "local_smoke"},
        }
    )
    pipeline.page_image_index_records = records
    pipeline.visual_retriever = FakeVisualRetriever()

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "page_image_rag",
        "What does the revenue chart show?",
        [],
        {"question": "What does the revenue chart show?", "modalities": ["figure"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("visual route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    top_record = metadata["page_image_index"][0]
    assert top_record["evidence_id"] == "page-image:file-b:6"
    assert metadata["visual_retriever_scores"]["page-image:file-b:6"] == 42.0
    assert top_record["metadata"]["visual_retriever"] == "fake_visual_retriever"
    assert top_record["metadata"]["visual_retriever_backend_type"] == "unit_test"


def test_mara_hybrid_route_skips_page_image_metadata_without_visual_backend(
    monkeypatch,
):
    def fail_page_image_build(*_args, **_kwargs):
        raise AssertionError("text hybrid route must not build page-image records")

    monkeypatch.setattr(
        route_retrieval,
        "build_local_page_image_records",
        fail_page_image_build,
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.selected_file_records = [{"file_id": "file-1", "path": "doc.pdf"}]
    docs = [
        RetrievedDocument(
            text="Revenue increased.",
            id_="doc-1",
            metadata={"file_id": "file-1", "page_label": "2"},
        )
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "hybrid_rag",
        "What happened to revenue?",
        [],
        {"question": "What happened to revenue?", "modalities": ["text"]},
        text_retrieve=lambda: (docs, []),
        metadata_builder=pipeline.build_evidence_metadata,
    )

    assert "page_image_index" not in metadata
    assert metadata["retrieval_info_count"] == 0


def test_mara_hybrid_route_skips_page_image_records_when_visual_route_disallowed():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = ["doc_text", "hybrid", "graph_global"]
    pipeline.page_image_index_records = _visual_page_records()
    docs = [
        RetrievedDocument(
            text="Revenue increased.",
            id_="doc-1",
            metadata={"file_id": "file-1", "page_label": "2"},
        )
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "hybrid_rag",
        "What happened to revenue?",
        [],
        {"question": "What happened to revenue?", "modalities": ["text"]},
        text_retrieve=lambda: (docs, []),
        metadata_builder=pipeline.build_evidence_metadata,
    )

    assert "page_image_index" not in metadata
    assert "visual_retriever_scores" not in metadata


def test_mara_hybrid_route_includes_page_image_metadata_with_visual_backend():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.page_image_index_records = _visual_page_records()

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "hybrid_rag",
        "What does the revenue chart show?",
        [],
        {"question": "What does the revenue chart show?", "modalities": ["figure"]},
        text_retrieve=lambda: ([], []),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert metadata["page_image_index"][0]["evidence_id"] == "page-image:file-b:5"


def test_mara_hybrid_route_generates_with_vlm_when_visual_evidence_available(
    monkeypatch,
):
    captured = {}

    class FakeVisualGenerator:
        name = "fake_vlm"

        def generate(self, request, bundle):
            captured["prompt"] = request.prompt
            captured["route"] = bundle.route
            captured["evidence_ids"] = [item["evidence_id"] for item in bundle.items]
            return "visual hybrid answer"

    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Hybrid"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "hybrid"
    pipeline.allowed_routes = ["hybrid", "doc_page_image", "doc_text"]
    pipeline.page_image_index_records = _visual_page_records()
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.vlm_generator = FakeVisualGenerator()
    pipeline.verification_mode = "off"
    monkeypatch.setattr(
        MaraAgentPipeline,
        "retrieve",
        lambda _self, _message, _history: ([], []),
    )

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "visual hybrid answer"
    ]
    assert captured == {
        "prompt": "What does the revenue chart show?",
        "route": "hybrid",
        "evidence_ids": ["page-image:file-b:5"],
    }


def test_mara_element_route_ranks_element_index_by_query():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.element_index_records = [
        {
            "evidence_id": "element:file-b:5:figure-1",
            "file_id": "file-b",
            "file_name": "tables.pdf",
            "page_label": "5",
            "element_id": "figure-1",
            "element_type": "figure",
            "modality": "figure",
            "caption": "Inventory diagram",
            "text": "Inventory was flat.",
            "source_backrefs": ["file-b#page:5"],
        },
        _element_record(),
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "What does the revenue table show?",
        [],
        {"question": "What does the revenue table show?", "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert (
        metadata["element_index"][0]["evidence_id"] == _element_record()["evidence_id"]
    )
    assert metadata["element_retriever_scores"][_element_record()["evidence_id"]] > (
        metadata["element_retriever_scores"]["element:file-b:5:figure-1"]
    )
    assert metadata["element_index"][0]["metadata"]["element_retriever"] == (
        "local_element_retriever"
    )


def test_mara_graph_route_retrieval_uses_graph_index_without_text_retrieval():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.graph_context = {
        "graph_index": {
            "community_summaries": [
                {
                    "id": "community-1",
                    "label": "Revenue System",
                    "summary": "Revenue connects report A and report B.",
                    "source_backrefs": ["file-a#page:2", "file-b#page:5"],
                }
            ]
        }
    }

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "graph_rag",
        "Compare revenue across reports.",
        [],
        {"question": "Compare revenue across reports.", "modalities": ["text"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("graph route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert metadata["graph_backend"] == "local_graph_index"
    assert metadata["graph_evidence"][0]["evidence_id"] == (
        "graph-community:community-1"
    )


def test_mara_graph_route_retrieval_uses_node_context_without_text_retrieval():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.graph_context = {
        "node_id": "component::strategy",
        "label": "Strategy",
        "summary": "Strategy connects pricing and roadmap themes.",
        "support_pages": {"file-a": ["2"]},
    }

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "graph_rag",
        "Compare strategy themes.",
        [],
        {"question": "Compare strategy themes.", "modalities": ["text"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("graph route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert metadata["graph_evidence"][0]["evidence_id"] == ("graph:component::strategy")
    assert metadata["graph_backend"] == "node_graph_context"


def test_mara_page_image_route_uses_configured_vlm_generator(monkeypatch):
    class FakeVLMGenerator:
        name = "fake_vlm_generator"

        def generate(self, _request, bundle):
            assert bundle.items[0]["modality"] == "page_image"
            return "The VLM saw a revenue chart."

    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Visual"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "visual"
    pipeline.page_image_index_records = _visual_page_records()
    pipeline.vlm_generator = FakeVLMGenerator()

    events = list(pipeline.stream("What does the revenue chart show?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "The VLM saw a revenue chart."
    ]


def test_mara_element_route_streams_element_answer_without_text_rag(monkeypatch):
    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Element"))
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "element"
    pipeline.element_index_records = [_element_record()]

    events = list(pipeline.stream("What does the revenue table show?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "Revenue increased in 2026."
    ]


def test_mara_strict_verifier_uses_rewrite_before_abstaining(monkeypatch):
    def unsupported_stream(_self, _message, _conv_id, _history, **_kwargs):
        yield Document(channel="chat", content="Profit declined sharply.")
        return Document(channel="chat", content="Profit declined sharply.")

    monkeypatch.setattr(FullQAPipeline, "stream", unsupported_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.verification_mode = "strict"
    pipeline.planner = lambda _payload: json.dumps(
        {"route": "doc", "reason": "Needs document text."}
    )
    pipeline.rewrite_generator = (
        lambda _request, _decision, _bundle, _answer: "Revenue increased in 2026."
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
        "Revenue increased in 2026."
    ]
