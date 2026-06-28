from local_backends.mara_evaluators import RAGTruthLocalEvaluator
from local_backends.mara_visual import local_visual_backend_health


def test_local_visual_backend_health_exposes_colqwen_qwen_vl_route_metadata(
    monkeypatch,
):
    from ktem.docqa import visual_backends

    monkeypatch.setattr(
        visual_backends,
        "_colvision_http_available",
        lambda endpoint, model_family: model_family == "colqwen",
    )
    monkeypatch.setattr(
        visual_backends,
        "_openai_compatible_vlm_available",
        lambda base_url: base_url.endswith("/v1"),
    )

    health = local_visual_backend_health(
        visual_retriever_backend="colqwen",
        visual_generator_backend="local_qwen3_vl",
    )

    assert health["backend_status"] == "configured"
    assert health["missing_backends"] == []
    assert health["backends"]["visual_retriever"]["name"] == "colqwen"
    assert health["backends"]["visual_generator"]["name"] == "local_qwen3_vl"


def test_local_visual_backend_health_requires_qwen_vl_endpoint(monkeypatch):
    from ktem.docqa import visual_backends

    monkeypatch.setattr(
        visual_backends,
        "_colvision_http_available",
        lambda endpoint, model_family: model_family == "colqwen",
    )
    monkeypatch.setattr(
        visual_backends,
        "_openai_compatible_vlm_available",
        lambda base_url: False,
    )

    health = local_visual_backend_health(
        visual_retriever_backend="colqwen",
        visual_generator_backend="local_qwen3_vl",
    )

    assert health["backend_status"] == "not_configured"
    assert health["missing_backends"] == ["visual_generator"]
    assert health["backends"]["visual_generator"]["status"] == "not_configured"


def test_local_evaluator_wrapper_returns_ragtruth_metrics_with_backend_metadata():
    evaluator = RAGTruthLocalEvaluator()

    result = evaluator(
        {
            "predicted_answer": "Revenue rose.",
            "gold_answers": ["revenue rose"],
            "metrics": {
                "unsupported_claim_count": 0.0,
                "unsupported_claim_rate": 0.0,
                "abstention_correctness": 1.0,
            },
            "verify_decision": {"contradictions": []},
        }
    )

    assert result["metrics"]["unsupported_claim_rate"] == 0.0
    assert result["metadata"]["implementation"] == "RAGTruthLocalEvaluator"
    assert result["metadata"]["backend"] == "local_proxy"
