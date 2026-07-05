from types import SimpleNamespace

from ktem.reasoning.mara import MaraAgentPipeline, _route_visual_answer
from ktem.reasoning.simple import FullQAPipeline


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


def test_mmdocrag_page_image_route_uses_ocr_first_before_vlm(monkeypatch):
    class FailingVLMGenerator:
        name = "must_not_run"

        def generate(self, _request, _bundle):
            raise AssertionError("OCR-first visual answer should skip VLM")

    monkeypatch.setattr(FullQAPipeline, "stream", _fail_if_text_rag_runs("Visual"))
    record = dict(_visual_page_records()[0])
    record["ocr_text"] = "The label is Market size."
    record["text"] = "The label is Market size."
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.route_policy = "visual"
    pipeline.verification_domain = "mmdocrag"
    pipeline.verification_mode = "off"
    pipeline.page_image_index_records = [record]
    pipeline.vlm_generator = FailingVLMGenerator()

    events = list(pipeline.stream("What label is shown?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "Market size"
    ]


def test_visual_route_caches_vlm_answer_by_page_and_prompt():
    class CountingVLMGenerator:
        name = "counting_vlm"

        def __init__(self):
            self.calls = 0

        def generate(self, _request, _bundle):
            self.calls += 1
            return "The VLM saw a revenue chart."

    generator = CountingVLMGenerator()
    pipeline = SimpleNamespace(vlm_generator=generator)
    request = SimpleNamespace(prompt="What does the chart show?", verification_domain="")
    bundle = SimpleNamespace(metadata={}, items=[_visual_page_records()[0]])
    cached_bundle = SimpleNamespace(metadata={}, items=[_visual_page_records()[0]])

    first = _route_visual_answer(
        pipeline,
        request,
        bundle,
        evidence_only_fallback=False,
    )
    second = _route_visual_answer(
        pipeline,
        request,
        cached_bundle,
        evidence_only_fallback=False,
    )

    assert first == second == "The VLM saw a revenue chart."
    assert generator.calls == 1
    assert bundle.metadata["vlm_cache"]["hit"] is False
    assert cached_bundle.metadata["vlm_cache"]["hit"] is True
