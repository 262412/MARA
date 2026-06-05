import json

from benchmark.engine_result import EngineRunResult
from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _WorkflowResultEngine:
    def __init__(self, _engine_name, _config):
        pass

    @staticmethod
    def run(*, example, documents):
        del example
        return EngineRunResult(
            answer="workflow answer",
            predicted_sources=[f"{documents[0].document_id}#page:1"],
            workflow_plan={
                "route": "hybrid",
                "steps": [{"executor": "retrieve_text"}],
            },
        )


def test_run_benchmark_preserves_workflow_plan_from_engine_result(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "workflow",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [{"route_id": "controller", "engine": "docqa_runtime"}],
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
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _WorkflowResultEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="workflow",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert report["predictions"][0]["workflow_plan"] == {
        "route": "hybrid",
        "steps": [{"executor": "retrieve_text"}],
    }
