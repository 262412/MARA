import json
import time

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _RequiresPrepareEngine:
    def __init__(self, engine_name, config, calls):
        self.engine_name = engine_name
        self.config = config
        self.calls = calls
        self.prepared = False

    def prepare_examples(self, _bundle, examples):
        time.sleep(0.03)
        self.calls.append(
            (
                self.engine_name,
                self.config.route,
                f"prepare:{','.join(example.example_id for example in examples)}",
            )
        )
        self.prepared = True

    def run_example(self, _bundle, example):
        if not self.prepared:
            raise AssertionError("engine was not prepared before route execution")
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


def test_run_benchmark_prepares_engine_outside_route_timeout(monkeypatch, tmp_path):
    manifest_path = _write_manifest(tmp_path)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _RequiresPrepareEngine(
            engine_name,
            config,
            calls,
        ),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="route_preparation",
            output_dir=tmp_path / "out",
            route_timeout_seconds=0.01,
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["error"] is None
    assert prediction["predicted_answer"] == "alpha"
    assert calls == [
        ("legacy_text_rag", "text_rag", "prepare:ex"),
        ("legacy_text_rag", "text_rag", "ex"),
    ]


def _write_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "timeout",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "text_rag",
                        "engine": "legacy_text_rag",
                        "scope": "document",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What is alpha?",
                        "answers": ["alpha"],
                        "evidence_pages": [1],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path
