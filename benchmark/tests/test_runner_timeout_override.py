import json

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _CaptureEngine:
    def __init__(self, config):
        self.config = config

    def run_example(self, _bundle, example):
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "alpha",
            "predicted_pages": [],
            "predicted_sources": [],
            "predicted_element_ids": [],
            "retrieved_hits": [],
        }


def test_explicit_run_timeout_overrides_lower_manifest_route_timeout(
    monkeypatch, tmp_path
):
    manifest_path = tmp_path / "manifest.json"
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "timeout",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "controller_auto",
                        "engine": "legacy_text_rag",
                        "route_timeout_seconds": 90,
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
    captured = []

    def fake_get_engine(_engine_name, config):
        engine = _CaptureEngine(config)
        captured.append(engine)
        return engine

    monkeypatch.setattr("benchmark.runner.get_engine", fake_get_engine)

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="route_timeout_override",
            output_dir=tmp_path / "out",
            route_timeout_seconds=240,
            use_generation=False,
        ),
    )

    assert captured[0].config.route_timeout_seconds == 240
    assert report["predictions"][0]["route_timeout_seconds"] == 240
