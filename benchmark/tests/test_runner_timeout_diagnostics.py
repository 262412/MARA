import json
import time

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _TracingSlowEngine:
    def run_example(self, _bundle, _example):
        time.sleep(1.0)
        return {"predicted_answer": "too late"}

    @staticmethod
    def route_timeout_diagnostics():
        return {
            "retrieval_trace": [
                {
                    "stage": "generation",
                    "status": "started",
                    "document_index_identity": "doc-v1",
                }
            ],
            "timings": {"index_seconds": 0.2},
            "cache": {
                "document_index": {
                    "hits": 1,
                    "misses": 0,
                    "identities": [{"document_id": "doc"}],
                }
            },
        }


def test_run_benchmark_preserves_stage_trace_when_route_times_out(
    monkeypatch,
    tmp_path,
):
    manifest_path = _write_single_route_manifest(tmp_path)
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda _engine_name, _config: _TracingSlowEngine(),
    )

    report = run_benchmark(
        str(manifest_path),
        BenchmarkConfig(
            suite_name="route_timeout_trace",
            output_dir=tmp_path / "out",
            route_timeout_seconds=0.01,
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["error_type"] == "route_timeout"
    assert prediction["retrieval_trace"] == [
        {
            "stage": "generation",
            "status": "started",
            "document_index_identity": "doc-v1",
        }
    ]
    assert prediction["timings"]["index_seconds"] == 0.2
    assert prediction["cache"]["document_index"]["hits"] == 1


def _write_single_route_manifest(tmp_path):
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
                        "route_id": "controller_auto",
                        "engine": "legacy_text_rag",
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
