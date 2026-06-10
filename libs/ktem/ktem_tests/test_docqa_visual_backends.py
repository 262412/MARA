from ktem.docqa import visual_backends
from ktem.docqa.visual_backends import (
    ColVisionHTTPVisualRetriever,
    QwenVLVisualGenerator,
    build_visual_generator_backend,
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


def test_colqwen_retriever_backend_calls_local_colvision_endpoint(
    monkeypatch,
):
    captured = {}

    monkeypatch.setenv("MARA_COLVISION_ENDPOINT", "http://127.0.0.1:8003/visual-score")
    monkeypatch.setattr(
        visual_backends,
        "_colvision_http_available",
        lambda endpoint, model_family: endpoint.endswith("/visual-score")
        and model_family == "colqwen",
    )

    def fake_post_json(self, payload):
        captured.update(payload)
        return {"scores": [0.8125], "model_family": self.model_family}

    monkeypatch.setattr(
        ColVisionHTTPVisualRetriever,
        "_post_json",
        fake_post_json,
    )

    health = visual_backend_health({"visual_retriever_backend": "colqwen"})
    backend = build_visual_retriever_backend("colqwen")

    assert health["backends"]["visual_retriever"] == {
        "name": "colqwen",
        "role": "visual_retriever",
        "status": "configured",
        "backend_type": "colvision_multi_vector",
        "benchmark_ready": True,
    }
    assert health["missing_backends"] == ["visual_generator"]
    assert backend.name == "colqwen"
    assert backend.model_family == "colqwen"
    assert backend.backend_type == "colvision_multi_vector"
    assert (
        backend.score(
            "revenue chart",
            {"page_image_path": "data:image/png;base64,abc", "page_label": "3"},
        )
        == 0.8125
    )
    assert captured == {
        "query": "revenue chart",
        "images": ["data:image/png;base64,abc"],
        "model_family": "colqwen",
    }


def test_local_qwen3_vl_generator_calls_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class _Message:
        content = "The chart shows revenue growth."

    class _Choice:
        message = _Message()

    class _Completions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type("Response", (), {"choices": [_Choice()]})()

    class _Client:
        chat = type("Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(QwenVLVisualGenerator, "_client", lambda _self: _Client())
    generator = QwenVLVisualGenerator()
    request = type("Request", (), {"prompt": "What does the chart show?"})()
    bundle = type(
        "Bundle",
        (),
        {
            "items": [
                {
                    "modality": "page_image",
                    "file_name": "report.pdf",
                    "page_label": "3",
                    "text": "Revenue chart.",
                    "page_image_path": "data:image/png;base64,abc",
                }
            ]
        },
    )()

    assert generator.generate(request, bundle) == "The chart shows revenue growth."
    assert captured["model"] == "Qwen/Qwen3-VL-8B-Instruct"
    assert captured["temperature"] == 0
    content = captured["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "What does the chart show?" in content[0]["text"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc"},
    }


def test_visual_backend_health_reports_local_qwen3_vl_generator(monkeypatch):
    monkeypatch.setenv("MARA_VLM_BASE_URL", "http://localhost:8001/v1")

    health = visual_backend_health(
        {
            "route_policy": "visual",
            "visual_retriever_backend": "local_late_interaction",
            "visual_generator_backend": "local_qwen3_vl",
            "requires_backend_config": True,
        }
    )

    assert health["backend_status"] == "configured"
    assert health["missing_backends"] == []
    assert health["backends"]["visual_generator"]["status"] == "configured"
    assert isinstance(
        build_visual_generator_backend("local_qwen3_vl"), QwenVLVisualGenerator
    )
