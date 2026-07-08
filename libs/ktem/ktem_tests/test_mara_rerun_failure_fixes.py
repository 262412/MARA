import json
from types import SimpleNamespace

import ktem.reasoning.mara_controller as mara_controller
from ktem.docqa.execution import _route_switch_candidates
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.mara_route_probe import controller_route_probe
from ktem.reasoning.mara_visual_gate import hybrid_should_use_visual_generator
from ktem.reasoning.simple import FullQAPipeline

from kotaemon.base import Document, RetrievedDocument


def _fake_answer_stream(_self, _message, _conv_id, _history, **_kwargs):
    yield Document(channel="chat", content="grounded answer")
    return Document(channel="chat", content="grounded answer")


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


def test_mara_stream_normalizes_llm_graph_route_for_visual_question(monkeypatch):
    captured = {}

    def graph_first_planner(_payload, _planner_model):
        return json.dumps(
            {
                "route": "graph",
                "reason": "The planner over-selected global graph evidence.",
            }
        )

    def fake_execute(
        self,
        message,
        conv_id,
        history,
        understanding,
        planner_payload,
        kwargs,
        **_extra,
    ):
        del self, message, conv_id, history, understanding, kwargs
        captured["planner_payload"] = dict(planner_payload)
        raise RuntimeError("stop after normalized planner")

    monkeypatch.setattr(
        mara_controller,
        "_run_planner_model",
        graph_first_planner,
        raising=False,
    )
    monkeypatch.setattr(MaraAgentPipeline, "execute_controller_route", fake_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner_model = "fake-planner"
    pipeline.allowed_routes = [
        "graph_global",
        "hybrid",
        "doc_text",
        "doc_page_image",
    ]
    pipeline.visual_retriever_backend = "colqwen"

    try:
        list(pipeline.stream("What slogan is shown on the slide?", "conv-1", []))
    except RuntimeError as exc:
        assert str(exc) == "stop after normalized planner"

    decision = captured["planner_payload"]["decision"]
    assert decision["route"] == "doc_page_image"
    assert decision["cost_gate_decision"] == "normalized_from_graph_global"
    assert decision["routing_features"]["visual_intent"] is True


def test_mara_stream_uses_visual_initial_route_without_route_switch(monkeypatch):
    class FakeVisualGenerator:
        name = "fake_vlm"

        def generate(self, _request, bundle):
            assert bundle.items[0]["evidence_id"] == "page-image:file-b:5"
            return "CARE. CONNECT. CAMPAIGN."

    def graph_first_planner(_payload, _planner_model):
        return json.dumps(
            {
                "route": "graph",
                "reason": "The planner over-selected global graph evidence.",
            }
        )

    monkeypatch.setattr(
        mara_controller,
        "_run_planner_model",
        graph_first_planner,
        raising=False,
    )
    monkeypatch.setattr(
        MaraAgentPipeline,
        "retrieve",
        lambda _self, _message, _history: ([], []),
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner_model = "fake-planner"
    pipeline.allowed_routes = [
        "graph_global",
        "hybrid",
        "doc_text",
        "doc_page_image",
    ]
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.page_image_index_records = _visual_page_records()
    pipeline.vlm_generator = FakeVisualGenerator()
    pipeline.verification_mode = "off"

    events = list(pipeline.stream("What slogan is shown on the slide?", "conv-1", []))

    execution_payloads = [
        event.content["payload"]
        for event in events
        if event.channel == "debug" and event.content.get("mara_channel") == "execution"
    ]
    assert execution_payloads
    decision = execution_payloads[0]["controller_decision"]
    assert decision["legacy_route"] == "doc_page_image"
    assert decision["initial_route"] == "doc_page_image"
    assert decision["final_route"] == "doc_page_image"
    assert decision["planner_route"] == "graph_global"
    assert decision["scored_route"] == "doc_page_image"
    assert decision["route_selection_policy"] == "cost_aware_initial"
    assert decision["route_switch_used"] is False
    assert decision["route_confidences"]["visual"] >= 0.6
    assert not any(
        item.get("stage") == "route_switch"
        for item in execution_payloads[0]["controller_trace"]
    )


def test_mara_stream_uses_text_initial_route_for_text_strong_question(monkeypatch):
    class FailingVisualGenerator:
        name = "must_not_run"

        def generate(self, _request, _bundle):
            raise AssertionError("text-strong controller route must not call VLM")

    def graph_first_planner(_payload, _planner_model):
        return json.dumps(
            {
                "route": "graph",
                "reason": "The planner over-selected global graph evidence.",
            }
        )

    monkeypatch.setattr(
        mara_controller,
        "_run_planner_model",
        graph_first_planner,
        raising=False,
    )
    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    docs = [
        RetrievedDocument(
            text="The annual report states that revenue increased.",
            id_="doc-1",
            metadata={"file_id": "file-b", "page_label": "5", "score": 0.91},
        )
    ]
    monkeypatch.setattr(
        MaraAgentPipeline,
        "retrieve",
        lambda _self, _message, _history: (docs, []),
    )
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.planner_model = "fake-planner"
    pipeline.allowed_routes = [
        "graph_global",
        "hybrid",
        "doc_text",
        "doc_page_image",
    ]
    pipeline.verification_domain = "mmdocrag"
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.page_image_index_records = _visual_page_records()
    pipeline.vlm_generator = FailingVisualGenerator()
    pipeline.verification_mode = "off"

    events = list(pipeline.stream("What happened to revenue?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "grounded answer"
    ]
    execution_payloads = [
        event.content["payload"]
        for event in events
        if event.channel == "debug" and event.content.get("mara_channel") == "execution"
    ]
    decision = execution_payloads[0]["controller_decision"]
    assert decision["legacy_route"] == "doc_text"
    assert decision["initial_route"] == "doc_text"
    assert decision["final_route"] == "doc_text"
    assert decision["planner_route"] == "graph_global"
    assert decision["scored_route"] == "doc_text"
    assert decision["route_switch_used"] is False
    assert decision["route_confidences"]["text"] >= 0.65


def test_route_switch_candidates_follow_cost_aware_order_for_visual_questions():
    request = SimpleNamespace(
        prompt="What slogan is shown on the slide?",
        allowed_routes=["graph_global", "hybrid", "doc_text", "doc_page_image"],
    )

    assert _route_switch_candidates(request, "graph_global") == [
        "doc_page_image",
        "doc_text",
        "hybrid",
    ]


def test_mara_hybrid_route_skips_vlm_for_text_strong_question(monkeypatch):
    class FailingVisualGenerator:
        name = "must_not_run"

        def generate(self, _request, _bundle):
            raise AssertionError("text-strong hybrid route must not call VLM")

    monkeypatch.setattr(FullQAPipeline, "stream", _fake_answer_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "hybrid"
    pipeline.allowed_routes = ["hybrid", "doc_page_image", "doc_text"]
    pipeline.page_image_index_records = _visual_page_records()
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.vlm_generator = FailingVisualGenerator()
    pipeline.verification_mode = "off"
    docs = [
        RetrievedDocument(
            text="The document states that revenue increased.",
            id_="doc-1",
            metadata={"file_id": "file-b", "page_label": "5"},
        )
    ]
    monkeypatch.setattr(
        MaraAgentPipeline,
        "retrieve",
        lambda _self, _message, _history: (docs, []),
    )

    events = list(pipeline.stream("What happened to revenue?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "grounded answer"
    ]


def test_hybrid_visual_gate_skips_mmdocrag_vlm_when_text_confidence_is_strong():
    bundle = SimpleNamespace(
        metadata={},
        items=[
            {"modality": "text", "text": "Revenue increased.", "evidence_id": "text"},
            {
                "modality": "page_image",
                "text": "Revenue chart.",
                "evidence_id": "page",
            },
        ],
    )
    request = SimpleNamespace(
        prompt="What does the revenue chart show?",
        verification_domain="mmdocrag",
    )
    decision = SimpleNamespace(
        reason="visual intent",
        route_confidences={"text": 0.72, "visual": 0.56},
        route_probe={"visual": {"top_margin": 0.03}},
    )

    assert hybrid_should_use_visual_generator(request, decision, bundle) is False
    assert bundle.metadata["visual_generation_gate"] == "skipped_text_strong"
    assert "doc_page_image" in bundle.metadata["skipped_expensive_routes"]


def test_mmdocrag_controller_probe_skips_visual_scoring_for_text_strong_table_question(
    monkeypatch,
):
    class FailingVisualRetriever:
        name = "must_not_score"
        backend_type = "unit_test"

        def score(self, _query, _record):
            raise AssertionError("text-strong MMDocRAG probe must not score images")

    docs = [
        RetrievedDocument(
            text=(
                "The amortisation and depreciation-related charge was 123 in "
                "2021 and 100 in 2020."
            ),
            id_=f"doc-{index}",
            metadata={
                "file_id": "inditex_2021",
                "file_name": "inditex_2021.pdf",
                "page_label": str(64 + index),
            },
            score=0.9,
        )
        for index in range(3)
    ]
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = [
        "graph_global",
        "hybrid",
        "doc_text",
        "doc_page_image",
    ]
    pipeline.dataset_family = "mmdocrag"
    pipeline.visual_retriever_backend = "colqwen"
    pipeline.visual_retriever = FailingVisualRetriever()
    pipeline.page_image_index_records = _visual_page_records()
    monkeypatch.setattr(
        MaraAgentPipeline,
        "retrieve",
        lambda _self, _message, _history: (docs, []),
    )

    probe = controller_route_probe(
        pipeline,
        (
            "What are the differences in the total amortisation and "
            "depreciation-related charges between 2021 and 2020?"
        ),
        [],
        {
            "question": (
                "What are the differences in the total amortisation and "
                "depreciation-related charges between 2021 and 2020?"
            ),
            "task_type": "qa",
            "modalities": ["table"],
            "available_modalities": ["page_image"],
            "scope": "document",
        },
    )

    assert "text" in probe
    assert "visual" not in probe
