import json

from benchmark.research_evaluators import (
    ALCEEvaluator,
    MMDocRAGEvaluator,
    RagasEvaluator,
    RAGTruthEvaluator,
)
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


def test_builtin_external_evaluator_adapters_mark_metric_categories():
    prediction = {
        "predicted_answer": "Revenue rose.",
        "gold_answers": ["revenue rose"],
        "metrics": {
            "citation_precision": 1.0,
            "citation_recall": 0.5,
            "f1": 0.75,
            "unsupported_claim_rate": 0.25,
            "multimodal_answer_support": 1.0,
        },
        "verify_decision": {"unsupported_claims": ["unsupported"]},
    }

    evaluators = [
        ALCEEvaluator(),
        MMDocRAGEvaluator(),
        RAGTruthEvaluator(),
        RagasEvaluator(),
    ]

    results = [evaluator(prediction) for evaluator in evaluators]

    assert [result["metadata"]["metric_category"] for result in results] == [
        "external_metric",
        "external_metric",
        "external_metric",
        "external_metric",
    ]
    assert results[0]["metadata"]["implementation"] == "ALCEEvaluator"
    assert results[3]["metrics"]["faithfulness"] == 0.75


def test_proxy_research_adapters_score_clean_final_answer_only():
    prediction = {
        "predicted_answer": (
            "<think>The answer might be profit declined.</think>\n\n"
            "Final answer: Revenue rose."
        ),
        "gold_answers": ["revenue rose"],
        "metrics": {
            "citation_precision": 1.0,
            "citation_recall": 1.0,
            "f1": 1.0,
            "unsupported_claim_rate": 0.0,
        },
        "verify_decision": {"unsupported_claims": []},
    }

    result = ALCEEvaluator()(prediction)

    assert result["metrics"]["fluency"] == 1.0
    assert result["metrics"]["correctness"] == 1.0


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
        "metric_category": "paper_grade_metric",
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


def test_run_benchmark_summarizes_external_evaluator_status_by_route(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "research_external_matrix",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["revenue rose"],
                    }
                ],
                "routes": [
                    {
                        "route_id": "paper",
                        "engine": "direct_paste",
                        "external_evaluators": {
                            "alce": (
                                "benchmark.tests.test_research_evaluators."
                                "fixture_alce_evaluator"
                            )
                        },
                    },
                    {
                        "route_id": "proxy_only",
                        "engine": "direct_paste",
                    },
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
            suite_name="research_external_matrix",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    by_route = report["summary"]["external_adapter_metric_metadata_by_route"]
    assert by_route["paper"]["alce"]["status"] == "configured"
    assert by_route["paper"]["alce"]["paper_grade"] is True
    assert by_route["proxy_only"]["alce"]["status"] == "not_configured"
    assert by_route["proxy_only"]["alce"]["excluded_from_summary"] is True
