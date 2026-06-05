from ktem.docqa import visual_backends
from ktem.docqa.visual_backends import (
    build_visual_retriever_backend,
    visual_backend_health,
)


def test_visual_backend_health_reports_required_vlm_readiness():
    health = visual_backend_health(
        {
            "route_policy": "visual",
            "visual_retriever_backend": "local_late_interaction",
            "generator_backend": "evidence_only_without_vlm",
            "requires_backend_config": True,
        }
    )

    assert health["backend_status"] == "not_configured"
    assert health["missing_backends"] == ["visual_generator"]
    assert health["backends"]["visual_retriever"]["status"] == "configured"
    assert health["backends"]["visual_generator"]["status"] == "evidence_only"


def test_colpali_retriever_backend_exposes_real_adapter_when_dependency_is_available(
    monkeypatch,
):
    monkeypatch.setattr(visual_backends, "_colpali_available", lambda: True)

    health = visual_backend_health({"visual_retriever_backend": "colpali"})
    backend = build_visual_retriever_backend("colpali")

    assert health["backends"]["visual_retriever"] == {
        "name": "colpali",
        "role": "visual_retriever",
        "status": "not_configured",
        "backend_type": "colvision_multi_vector",
        "benchmark_ready": False,
        "readiness_reason": "requires_real_colvision_inference_backend",
    }
    assert health["missing_backends"] == ["visual_retriever", "visual_generator"]
    assert backend.name == "colpali"
    assert backend.model_family == "colpali"
    assert backend.backend_type == "colvision_multi_vector"
    assert backend.score("revenue chart", {"text": "revenue chart"}) == 0.0
    assert backend.score("revenue chart", {"page_level_score": 0.83}) == 0.83
