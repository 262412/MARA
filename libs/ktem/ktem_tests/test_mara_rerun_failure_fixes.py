import json
from types import SimpleNamespace

import ktem.reasoning.mara_controller as mara_controller
from ktem.docqa.execution import _route_switch_candidates
from ktem.reasoning.mara import MaraAgentPipeline
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
