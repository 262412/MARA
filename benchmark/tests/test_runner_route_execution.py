import json

from benchmark.route_execution import route_skip_record
from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _FakeEngine:
    def __init__(self, engine_name, config, calls):
        self.engine_name = engine_name
        self.config = config
        self.calls = calls

    def run_example(self, bundle, example):
        self.calls.append((self.engine_name, self.config.route, example.example_id))
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "alpha",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
        }


def test_run_benchmark_skips_not_configured_routes(monkeypatch, tmp_path):
    manifest_path = _write_skip_manifest(tmp_path)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config, calls),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="skip_routes",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert calls == [("legacy_text_rag", "text", "ex")]
    assert [item["route"] for item in report["predictions"]] == ["text"]
    assert report["summary"]["num_executed_routes"] == 1
    assert report["summary"]["num_skipped_routes"] == 1
    assert report["summary"]["skipped_routes"] == [_expected_skip_record()]
    assert report["summary"]["backend_metadata"]["vlm"]["backend_status"] == (
        "not_configured"
    )


def test_run_benchmark_propagates_visual_backend_route_fields(monkeypatch, tmp_path):
    manifest_path = _write_visual_backend_manifest(tmp_path)
    captured_configs = []

    def fake_get_engine(engine_name, config):
        captured_configs.append(config)
        return _FakeEngine(engine_name, config, [])

    monkeypatch.setattr("benchmark.runner.get_engine", fake_get_engine)

    run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="visual_backends",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert captured_configs[0].visual_retriever_backend == "local_late_interaction"
    assert captured_configs[0].visual_generator_backend == "tests.fake_vlm"
    assert captured_configs[0].generator_backend == "tests.fake_vlm"


def test_route_skip_record_uses_visual_backend_readiness_for_required_vlm():
    record = route_skip_record(
        {
            "route_policy": "visual",
            "visual_retriever_backend": "local_late_interaction",
            "generator_backend": "evidence_only_without_vlm",
            "requires_backend_config": True,
        },
        route_id="page_image_rag_vlm",
        engine="docqa_runtime",
    )

    assert record == {
        "route_id": "page_image_rag_vlm",
        "engine": "docqa_runtime",
        "backend_status": "not_configured",
        "requires_backend_config": True,
        "missing_backends": ["visual_generator"],
        "skip_reason": "not_configured: visual_generator",
    }


def _write_skip_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_skip_manifest_payload()), encoding="utf-8")
    return manifest_path


def _write_visual_backend_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "visual.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "visual_backends",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "visual",
                        "engine": "docqa_runtime",
                        "route_policy": "visual",
                        "visual_retriever_backend": "local_late_interaction",
                        "generator_backend": "tests.fake_vlm",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What is alpha?",
                        "answers": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _skip_manifest_payload():
    return {
        "schema_version": 2,
        "dataset_name": "skip_routes",
        "documents": [{"document_id": "doc", "path": "doc.txt"}],
        "routes": [
            {"route_id": "text", "engine": "legacy_text_rag"},
            {
                "route_id": "vlm",
                "engine": "docqa_runtime",
                "backend_status": "not_configured",
                "requires_backend_config": True,
                "missing_backends": ["colpali", "visual_generator"],
            },
        ],
        "examples": [
            {
                "example_id": "ex",
                "document_id": "doc",
                "question": "What is alpha?",
                "answers": ["alpha"],
            }
        ],
    }


def _expected_skip_record():
    return {
        "route_id": "vlm",
        "engine": "docqa_runtime",
        "backend_status": "not_configured",
        "requires_backend_config": True,
        "missing_backends": ["colpali", "visual_generator"],
        "skip_reason": "not_configured: colpali, visual_generator",
    }
