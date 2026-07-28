import json

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _FakeEngine:
    def __init__(self, engine_name, config, calls):
        self.engine_name = engine_name
        self.config = config
        self.calls = calls

    def run_example(self, bundle, example):
        self.calls.append((self.engine_name, self.config.route, example.example_id))
        document_ids = example.document_ids or [example.document_id]
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": f"{self.engine_name}:{self.config.route}",
            "predicted_pages": [1],
            "predicted_sources": [f"{document_ids[0]}#page:1"],
            "predicted_citations": [f"{document_ids[0]}#page:1"],
            "scored_predicted_sources": [f"{document_ids[0]}#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [
                {
                    "doc_id": "hit-1",
                    "document_id": document_ids[0],
                    "page_label": "1",
                    "score": 1.0,
                }
            ],
            "retrieval_trace": {
                "route": self.config.route,
                "engine": self.engine_name,
                "retrieved_elements": ["hit-1"],
            },
            "agent_trace": [{"stage": "planner", "route": self.config.route}],
            "controller_trace": [
                {"stage": "planner", "route": "graph_global"},
            ],
            "workflow_plan": {
                "steps": [
                    {"stage": "retrieve", "action": "retry", "retry": True},
                    {
                        "stage": "route_switch",
                        "from_route": "doc_text",
                        "to_route": "graph_global",
                    },
                ]
            },
            "route_decision": {"route": "graph_global"},
            "retrieve_decision": {"status": "good"},
            "verify_decision": {"status": "supported"},
            "evidence_bundle": {"route": "graph_global", "items": []},
            "timings": {
                "parse_seconds": 0.1,
                "index_seconds": 0.2,
                "retrieval_seconds": 0.01,
                "generation_seconds": 0.02,
            },
            "performance": {
                "parse_seconds": 0.1,
                "index_seconds": 0.2,
                "retrieval_seconds": 0.01,
                "generation_seconds": 0.02,
                "total_seconds": 0.33,
            },
            "cache": {
                "parse": {"hits": 1, "misses": 0, "writes": 0},
                "embedding": {"hits": 2, "misses": 1, "writes": 1},
            },
            "cost": {"estimated_usd": 0.0},
            "context_preview": "context",
        }

    def document_reports(self):
        return [{"engine": self.engine_name, "route": self.config.route}]


def _assert_controller_trace_fields(report):
    assert report["predictions"][0]["controller_trace"] == [
        {"stage": "planner", "route": "graph_global"}
    ]
    assert report["retrieval_traces"][0]["route_decision"] == {"route": "graph_global"}
    assert report["retrieval_traces"][0]["evidence_bundle"] == {
        "route": "graph_global",
        "items": [],
    }


def _assert_trace_citation_fields(report):
    assert report["retrieval_traces"][0]["predicted_sources"] == ["doc#page:1"]
    assert report["retrieval_traces"][0]["predicted_citations"] == ["doc#page:1"]
    assert report["retrieval_traces"][0]["scored_predicted_sources"] == ["doc#page:1"]


def _assert_verifier_observability_fields(report):
    assert report["predictions"][0]["verifier_observability"]["retry_count"] == 1
    assert report["predictions"][0]["verifier_observability"]["route_switch_count"] == 1
    assert report["summary"]["num_retry"] == 2
    assert report["summary"]["num_route_switch"] == 2
    assert report["summary"]["verifier_observability_by_route"][0]["num_retry"] == 1


def test_run_benchmark_expands_manifest_route_matrix(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "routes",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "page_fast",
                        "engine": "legacy_text_rag",
                        "scope": "page",
                        "retrieval_mode": "text",
                    },
                    {
                        "route_id": "direct",
                        "engine": "direct_paste",
                        "scope": "document",
                    },
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "scope": "page",
                        "question": "What is alpha?",
                        "answers": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, str, str]] = []

    def fake_get_engine(engine_name, config):
        return _FakeEngine(engine_name, config, calls)

    monkeypatch.setattr("benchmark.runner.get_engine", fake_get_engine)

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="routes",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert calls == [
        ("legacy_text_rag", "page_fast", "ex"),
        ("direct_paste", "direct", "ex"),
    ]
    assert [item["route"] for item in report["predictions"]] == ["page_fast", "direct"]
    assert [item["engine"] for item in report["predictions"]] == [
        "legacy_text_rag",
        "direct_paste",
    ]
    assert report["summary"]["num_routes"] == 2
    assert report["summary"]["avg_parse_seconds"] == 0.1
    assert report["summary"]["avg_index_seconds"] == 0.2
    assert report["summary"]["parse_cache_hits"] == 2
    assert report["summary"]["parse_cache_misses"] == 0
    assert report["summary"]["parse_cache_hit_rate"] == 1.0
    assert report["summary"]["embedding_cache_hits"] == 4
    assert report["summary"]["embedding_cache_misses"] == 2
    assert report["summary"]["embedding_cache_hit_rate"] == 0.6667
    _assert_verifier_observability_fields(report)
    assert len(report["retrieval_traces"]) == 2
    expected_agent_trace = [{"stage": "planner", "route": "page_fast"}]
    assert report["predictions"][0]["agent_trace"] == expected_agent_trace
    assert report["retrieval_traces"][0]["agent_trace"] == expected_agent_trace
    _assert_trace_citation_fields(report)
    _assert_controller_trace_fields(report)
    assert report["retrieval_traces"][0]["performance"]["parse_seconds"] == 0.1
    assert report["retrieval_traces"][0]["cache"]["parse"]["hits"] == 1


def test_run_benchmark_filters_manifest_route_by_id(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {"route_id": "skip", "engine": "legacy_text_rag"},
                    {"route_id": "keep", "engine": "oracle_page"},
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
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config, calls),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="routes",
            output_dir=tmp_path / "out",
            route="keep",
            use_generation=False,
        ),
    )

    assert calls == [("oracle_page", "keep", "ex")]
    assert len(report["predictions"]) == 1
    assert report["predictions"][0]["route"] == "keep"


def _write_format_guardrail_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "format_guardrails",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "format-ex",
                        "document_id": "doc",
                        "question": "Summarize the table and formula.",
                        "answers": ["Encoder uses self-attention."],
                        "expected_formats": ["markdown_table", "latex"],
                        "expected_guardrails": {
                            "allow_abstention": False,
                            "rewrite_skipped": True,
                        },
                        "modality": "figure",
                        "gold_evidence": [{"element_type": "formula"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_run_benchmark_scores_format_and_guardrail_fields(monkeypatch, tmp_path):
    class _GuardrailEngine:
        def __init__(self, engine_name, config):
            self.engine_name = engine_name
            self.config = config

        def run_example(self, bundle, example):
            return {
                "example_id": example.example_id,
                "document_id": example.document_id,
                "question": example.question,
                "gold_answers": example.answers,
                "gold_pages": example.evidence_pages,
                "gold_sources": example.evidence_sources,
                "predicted_answer": (
                    "| Component | Mechanism |\n"
                    "| :--- | :--- |\n"
                    "| Encoder | Self-attention |\n\n"
                    r"The formula is $w_{t+1}=w_t-\eta\nabla L$."
                ),
                "predicted_pages": [],
                "predicted_sources": [],
                "predicted_element_ids": [],
                "retrieved_hits": [],
                "claim_verification": {
                    "abstained": False,
                    "rewrite_skipped": True,
                },
                "verify_decision": {
                    "status": "unsupported",
                    "action": "revise",
                    "unsupported_claims": ["The model invented a citation."],
                    "verified_citations": ["doc#page:1"],
                },
                "evidence_metadata": {
                    "has_formula_evidence": True,
                    "has_figure_evidence": True,
                },
            }

        def document_reports(self):
            return []

    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _GuardrailEngine(engine_name, config),
    )

    report = run_benchmark(
        _write_format_guardrail_manifest(tmp_path),
        BenchmarkConfig(
            suite_name="format_guardrails",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["expected_formats"] == ["markdown_table", "latex"]
    assert prediction["expected_guardrails"]["rewrite_skipped"] is True
    assert prediction["evidence_metadata"]["has_formula_evidence"] is True
    assert prediction["metrics"]["figure_hit"] == 1.0
    assert prediction["metrics"]["formula_hit"] == 1.0
    assert prediction["metrics"]["table_hit"] is None
    assert prediction["metrics"]["markdown_table_renderable"] == 1.0
    assert prediction["metrics"]["latex_renderable"] == 1.0
    assert prediction["metrics"]["false_abstention"] == 0.0
    assert prediction["metrics"]["rewrite_skipped"] == 1.0
    assert prediction["metrics"]["guardrail_expectation_match"] == 1.0
    assert prediction["metrics"]["unsupported_claim_rate"] == 1.0
    assert prediction["metrics"]["not_enough_evidence_rate"] == 0.0
    assert prediction["metrics"]["unsupported_claim_count"] == 1.0
    assert prediction["metrics"]["verified_citation_count"] == 1.0
    assert report["summary"]["avg_markdown_table_renderable"] == 1.0
    assert report["summary"]["avg_figure_hit"] == 1.0
    assert report["summary"]["avg_formula_hit"] == 1.0
    assert report["summary"]["avg_latex_renderable"] == 1.0
    assert report["summary"]["avg_false_abstention"] == 0.0
    assert report["summary"]["avg_guardrail_expectation_match"] == 1.0
    assert report["summary"]["avg_unsupported_claim_rate"] == 1.0
    assert report["summary"]["avg_not_enough_evidence_rate"] == 0.0
    assert report["summary"]["avg_unsupported_claim_count"] == 1.0
    assert report["summary"]["avg_verified_citation_count"] == 1.0


def test_run_benchmark_scores_mmdocrag_visual_support_fields(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "mmdocrag",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "visual-ex",
                        "document_id": "doc",
                        "question": "What does the chart show?",
                        "answers": ["revenue rose"],
                        "gold_evidence": [
                            {
                                "modality": "page_image",
                                "image_quote": "revenue rose",
                                "hard_negative_ids": ["page-image:negative"],
                            },
                            {"element_type": "table"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class _VisualEngine:
        def __init__(self, engine_name, config):
            self.engine_name = engine_name
            self.config = config

        def run_example(self, bundle, example):
            return {
                "example_id": example.example_id,
                "document_id": example.document_id,
                "question": example.question,
                "gold_answers": example.answers,
                "gold_pages": example.evidence_pages,
                "gold_sources": example.evidence_sources,
                "predicted_answer": "The chart shows revenue rose in 2026.",
                "predicted_pages": [],
                "predicted_sources": [],
                "predicted_element_ids": [],
                "retrieved_hits": [{"modality": "table"}],
                "evidence_bundle": {
                    "items": [
                        {"modality": "page_image"},
                        {"modality": "table"},
                    ]
                },
            }

        def document_reports(self):
            return []

    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _VisualEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="mmdocrag",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["metrics"]["image_quote_hit"] == 1.0
    assert prediction["metrics"]["multimodal_answer_support"] == 1.0
    assert prediction["metrics"]["hard_negative_rejection"] == 1.0
    assert report["summary"]["avg_image_quote_hit"] == 1.0
    assert report["summary"]["avg_multimodal_answer_support"] == 1.0
    assert report["summary"]["avg_hard_negative_rejection"] == 1.0


def _write_research_adapter_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "research_adapters",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What does the chart show?",
                        "answers": ["revenue rose"],
                        "gold_evidence": [
                            {
                                "modality": "page_image",
                                "image_quote": "revenue rose",
                                "citation": "doc#page:1",
                            }
                        ],
                    }
                ],
                "routes": [
                    {
                        "route_id": "controller_auto",
                        "engine": "docqa_runtime",
                        "planner_backend": "heuristic_local",
                        "generator_backend": "fixture_generator",
                        "text_retriever_backend": "fixture_text",
                        "visual_retriever_backend": "local_late_interaction",
                        "visual_backend_type": "deterministic_smoke",
                        "graph_backend": "local_graph",
                        "implementation_stage": "proxy_evaluator_fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


class _ResearchEngine:
    def __init__(self, engine_name, config):
        self.engine_name = engine_name
        self.config = config

    def run_example(self, bundle, example):
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "The chart shows revenue rose.",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
            "evidence_bundle": {"items": [{"modality": "page_image"}]},
            "verify_decision": {
                "status": "supported",
                "unsupported_claims": [],
                "contradictions": [],
            },
        }

    def document_reports(self):
        return []


def test_run_benchmark_reports_named_research_adapters_and_backends(
    monkeypatch, tmp_path
):
    manifest_path = _write_research_adapter_manifest(tmp_path)

    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _ResearchEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="research_adapters",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    adapter_metrics = report["predictions"][0]["adapter_metrics"]
    adapter_metadata = report["predictions"][0]["adapter_metric_metadata"]
    assert set(adapter_metrics) == {"alce", "mmdocrag", "ragas", "ragtruth"}
    assert adapter_metadata["alce"]["metric_scope"] == "proxy"
    assert adapter_metadata["alce"]["metric_category"] == "proxy_metric"
    assert adapter_metadata["alce"]["paper_grade"] is False
    assert adapter_metadata["mmdocrag"]["metric_scope"] == "proxy"
    assert adapter_metadata["ragas"]["metric_scope"] == "proxy"
    assert adapter_metadata["ragtruth"]["metric_scope"] == "proxy"
    assert report["summary"]["adapter_metric_metadata"] == adapter_metadata
    assert {
        "fluency",
        "correctness",
        "citation_recall",
        "citation_precision",
        "attributable_claim_rate",
    } <= set(adapter_metrics["alce"])
    assert {
        "page_hit",
        "element_hit",
        "image_quote_hit",
        "cross_page_evidence_hit",
        "multimodal_answer_support",
    } <= set(adapter_metrics["mmdocrag"])
    assert {
        "unsupported_claim_count",
        "unsupported_claim_rate",
        "contradiction_count",
        "abstention_correctness",
    } <= set(adapter_metrics["ragtruth"])
    assert {
        "context_precision",
        "context_recall",
        "faithfulness",
        "response_relevancy",
    } <= set(adapter_metrics["ragas"])
    assert adapter_metrics["alce"]["correctness"] == 1.0
    assert adapter_metrics["alce"]["citation_recall"] == 0.0
    assert adapter_metrics["mmdocrag"]["image_quote_hit"] == 1.0
    assert adapter_metrics["ragtruth"]["unsupported_claim_rate"] == 0.0
    assert adapter_metrics["ragas"]["faithfulness"] == 1.0
    assert adapter_metrics["ragtruth"]["contradiction_count"] == 0.0
    assert report["summary"]["backend_metadata"]["controller_auto"] == {
        "text_retriever": "fixture_text",
        "visual_retriever": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "graph_backend": "local_graph",
        "planner_backend": "heuristic_local",
        "generator_backend": "fixture_generator",
        "implementation_stage": "proxy_evaluator_fixture",
    }


def test_run_benchmark_handles_empty_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 2, "documents": [], "examples": []}),
        encoding="utf-8",
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="empty",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert report["summary"]["num_examples"] == 0
    assert report["summary"]["avg_em"] is None
    assert report["predictions"] == []
    assert report["retrieval_traces"] == []
