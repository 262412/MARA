import json

from benchmark.research_evaluators import (
    ALCEEvaluator,
    MMDocRAGEvaluator,
    RagasEvaluator,
    RAGTruthEvaluator,
    external_research_adapter_metrics,
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


def fixture_alce_primary_evaluator(prediction):
    return {
        "metrics": {
            "official_answer_score": 0.42,
            "official_citation_score": 0.75,
        },
        "metadata": {
            "paper_grade": True,
            "primary_metric": "official_answer_score",
            "contract_id": "alce_official_judge_v1",
            "implementation": "fixture_alce_primary_external",
        },
    }


def fixture_alce_override_evaluator(prediction):
    return {
        "metrics": {"official_answer_score": 0.84},
        "metadata": {
            "paper_grade": True,
            "primary_metric": "official_answer_score",
            "contract_id": "alce_route_override_judge_v1",
            "implementation": "fixture_alce_override_external",
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


def test_builtin_proxy_evaluator_alias_is_configured_but_not_paper_grade():
    prediction = {
        "predicted_answer": "Revenue rose.",
        "gold_answers": ["revenue rose"],
        "metrics": {
            "citation_precision": 1.0,
            "citation_recall": 0.5,
            "f1": 0.75,
            "unsupported_claim_rate": 0.25,
        },
    }

    metrics, metadata = external_research_adapter_metrics(
        prediction,
        {"external_evaluators": {"alce": "builtin:alce_proxy"}},
    )

    assert metadata["alce"]["status"] == "configured"
    assert metadata["alce"]["backend"] == "builtin:alce_proxy"
    assert metadata["alce"]["paper_grade"] is False
    assert metadata["alce"]["metric_category"] == "external_metric"
    assert metrics["alce"]["correctness"] == 1.0


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


def test_run_benchmark_promotes_paper_grade_external_metric_to_headline_score(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "alce_asqa",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["correct answer"],
                    }
                ],
                "routes": [
                    {
                        "route_id": "paper",
                        "engine": "direct_paste",
                        "external_evaluators": {
                            "alce": (
                                "benchmark.tests.test_research_evaluators."
                                "fixture_alce_primary_evaluator"
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
        str(manifest_path),
        BenchmarkConfig(
            suite_name="research_external_primary",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["metrics"]["local_native_score"] == 0.0
    assert prediction["metrics"]["paper_grade_score"] == 0.42
    assert prediction["metrics"]["native_score"] == 0.42
    assert prediction["metrics"]["mara_score"] == 0.42
    assert prediction["mara_scoring_source"] == "external_paper_grade"
    assert prediction["mara_scoring_contract"] == "alce_official_judge_v1"
    assert prediction["mara_primary_metric"] == "official_answer_score"
    assert report["summary"]["avg_mara_score"] == 0.42
    assert report["summary"]["mara_score_metadata"]["scoring_mode"] == (
        "paper_grade_external_v1"
    )


def test_run_benchmark_uses_configured_external_evaluator_for_single_route(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "alce_asqa",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["correct answer"],
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
        str(manifest_path),
        BenchmarkConfig(
            suite_name="research_external_primary_config",
            output_dir=tmp_path / "out",
            engine="direct_paste",
            route="paper",
            external_evaluators={
                "alce": (
                    "benchmark.tests.test_research_evaluators."
                    "fixture_alce_primary_evaluator"
                )
            },
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["external_adapter_metric_metadata"]["alce"]["status"] == (
        "configured"
    )
    assert prediction["metrics"]["paper_grade_score"] == 0.42
    assert prediction["metrics"]["mara_score"] == 0.42


def test_manifest_route_external_evaluator_overrides_config_default(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "alce_asqa",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["correct answer"],
                    }
                ],
                "routes": [
                    {
                        "route_id": "paper",
                        "engine": "direct_paste",
                        "external_evaluators": {
                            "alce": (
                                "benchmark.tests.test_research_evaluators."
                                "fixture_alce_override_evaluator"
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
        str(manifest_path),
        BenchmarkConfig(
            suite_name="research_external_primary_override",
            output_dir=tmp_path / "out",
            external_evaluators={
                "alce": (
                    "benchmark.tests.test_research_evaluators."
                    "fixture_alce_primary_evaluator"
                )
            },
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["metrics"]["paper_grade_score"] == 0.84
    assert prediction["mara_scoring_contract"] == "alce_route_override_judge_v1"


def test_run_benchmark_does_not_promote_builtin_proxy_external_evaluator(
    monkeypatch, tmp_path
):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "alce_asqa",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened?",
                        "answers": ["correct answer"],
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
        str(manifest_path),
        BenchmarkConfig(
            suite_name="research_external_builtin_proxy",
            output_dir=tmp_path / "out",
            engine="direct_paste",
            route="paper",
            external_evaluators={"alce": "builtin:alce_proxy"},
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["external_adapter_metric_metadata"]["alce"]["status"] == (
        "configured"
    )
    assert prediction["external_adapter_metric_metadata"]["alce"]["paper_grade"] is (
        False
    )
    assert "paper_grade_score" not in prediction["metrics"]
    assert prediction["metrics"]["mara_score"] == prediction["metrics"]["native_score"]
    assert report["summary"]["mara_score_metadata"]["paper_grade"] is False


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
