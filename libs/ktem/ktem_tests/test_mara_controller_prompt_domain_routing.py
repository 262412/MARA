from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.mara_route_scorer import score_adaptive_route


def test_mara_stream_routes_on_controller_question_not_benchmark_prompt(monkeypatch):
    captured = {}

    def fake_execute(
        self,
        message,
        conv_id,
        history,
        understanding,
        planner_payload,
        kwargs,
        **extra,
    ):
        del self, conv_id, history, kwargs
        captured["message"] = message
        captured["extra"] = dict(extra)
        captured["understanding"] = dict(understanding)
        captured["decision"] = dict(planner_payload["decision"])
        raise RuntimeError("stop after planner")

    monkeypatch.setattr(MaraAgentPipeline, "execute_controller_route", fake_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
    raw_question = (
        "Compare the ownership status and geographical distribution of PepsiCo's "
        "properties with the financial performance metrics for 2020 and 2019."
    )
    pipeline.controller_question = raw_question
    pipeline.dataset_family = "mmdocrag"
    pipeline.visual_retriever_backend = "colqwen"
    benchmark_prompt = (
        "Benchmark gold-answer contract:\n"
        "Use the provided evidence only. Return only the gold-answer value that "
        "should be compared against the dataset reference answer.\n"
        "For visual/page QA, output the visible answer text exactly as it should "
        "be scored.\n"
        f"Question: {raw_question}\n"
        "Answer:"
    )

    try:
        list(pipeline.stream(benchmark_prompt, "conv-1", []))
    except RuntimeError as exc:
        assert str(exc) == "stop after planner"

    assert captured["message"] == benchmark_prompt
    assert captured["extra"]["routing_message"] == raw_question
    assert captured["understanding"]["task_type"] == "compare"
    assert captured["understanding"]["modalities"] == ["text"]
    assert captured["decision"]["route"] == "doc_text"
    assert captured["decision"]["routing_features"]["visual_intent"] is False
    assert captured["decision"]["latency_budget"]["dataset_family"] == "mmdocrag"


def test_mmdocrag_text_strong_caps_effective_visual_confidence():
    decision = score_adaptive_route(
        {
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["page_image"],
            "scope": "multi_document",
        },
        question=(
            "Compare the ownership status and geographical distribution of PepsiCo's "
            "properties with the financial performance metrics for 2020 and 2019."
        ),
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
        route_probe={
            "text": {
                "evidence_count": 12,
                "top_score": 0.7,
                "top_margin": 0.12,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
            },
            "visual": {
                "evidence_count": 200,
                "top_score": 1.0,
                "top_margin": 0.0,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
                "backend_healthy": True,
            },
        },
        dataset_family="mmdocrag",
        latency_budget={"dataset_family": "mmdocrag"},
    )

    assert decision["route"] == "doc_text"
    assert decision["raw_route_confidence_by_modality"]["visual"] > 0.8
    assert decision["route_confidence_by_modality"]["visual"] <= 0.45
    assert "doc_page_image" in decision["cost_gate_enforced_routes"]
    assert decision["cost_gate_decision"] == "text_cost_gate_passed"
