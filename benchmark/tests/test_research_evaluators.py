import json

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


def fixture_alce_evaluator(prediction):
    assert prediction["example_id"] == "ex"
    return {
        "metrics": {
            "answer_precision": 0.75,
            "citation_attribution": 1.0,
        },
        "metadata": {
            "paper_grade": True,
            "implementation": "fixture_alce_external",
        },
    }


class _ExternalEvaluatorEngine:
    def __init__(self, engine_name, config):
        self.engine_name = engine_name
        self.config = config

    @staticmethod
    def run_example(_bundle, example):
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "Revenue rose.",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
        }

    @staticmethod
    def document_reports():
        return []


def test_run_benchmark_reports_external_research_evaluator_status(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "research_external",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["revenue rose"],
                        "gold_evidence": [{"citation": "doc#page:1"}],
                    }
                ],
                "routes": [
                    {
                        "route_id": "external_eval",
                        "engine": "direct_paste",
                        "external_evaluators": {
                            "alce": (
                                "benchmark.tests.test_research_evaluators."
                                "fixture_alce_evaluator"
                            )
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _ExternalEvaluatorEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="research_external",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["adapter_metric_metadata"]["alce"]["metric_scope"] == "proxy"
    assert prediction["external_adapter_metrics"] == {
        "alce": {
            "answer_precision": 0.75,
            "citation_attribution": 1.0,
        }
    }
    assert prediction["external_adapter_metric_metadata"]["alce"] == {
        "backend": ("benchmark.tests.test_research_evaluators.fixture_alce_evaluator"),
        "implementation": "fixture_alce_external",
        "metric_scope": "external",
        "paper_grade": True,
        "status": "configured",
    }
    assert prediction["external_adapter_metric_metadata"]["mmdocrag"]["status"] == (
        "not_configured"
    )
    assert prediction["external_adapter_metric_metadata"]["ragtruth"]["status"] == (
        "not_configured"
    )
    assert report["summary"]["external_adapter_metric_metadata"] == (
        prediction["external_adapter_metric_metadata"]
    )
