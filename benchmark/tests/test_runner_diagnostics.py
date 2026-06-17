import json

from benchmark.diagnostics import prediction_diagnostics
from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _DiagnosticEngine:
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
            "predicted_answer": (
                "<think>Scratch.</think>\n\n" "Final answer: Revenue increased in 2026."
            ),
            "predicted_pages": [2],
            "predicted_sources": ["doc#page:2"],
            "predicted_element_ids": [],
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ],
            "route_decision": {"route": "doc_text"},
            "verify_decision": {"status": "supported"},
            "guardrail_decision": {"action": "return"},
            "evidence_bundle": {
                "items": [
                    {
                        "document_id": "doc",
                        "page_label": "2",
                        "text": "Revenue increased in 2026.",
                    }
                ]
            },
        }

    @staticmethod
    def document_reports():
        return []


def test_run_benchmark_adds_generic_route_diagnostics(monkeypatch, tmp_path):
    manifest_path = _write_diagnostic_manifest(tmp_path)
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _DiagnosticEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="diagnostics",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    diagnostics = report["predictions"][0]["diagnostics"]
    assert diagnostics["retrieved_count"] == 1
    assert diagnostics["evidence_item_count"] == 1
    assert diagnostics["gold_document_hit"] == 1.0
    assert diagnostics["gold_page_hit"] == 1.0
    assert diagnostics["gold_span_hit"] == 1.0
    assert diagnostics["answer_nonempty_after_cleaning"] == 1.0
    assert diagnostics["verifier_status"] == "supported"
    assert diagnostics["guardrail_action"] == "return"
    assert diagnostics["retrieval_failure_type"] == "none"
    assert diagnostics["citation_failure_type"] == "none"
    assert diagnostics["failure_class"] == "none"
    assert diagnostics["controller_selected_route"] == "doc_text"
    assert "doc_text" in diagnostics["recommended_routes"]
    assert report["summary"]["dataset_route_diagnostics"] == [
        {
            "dataset_name": "qasper",
            "route": "controller_auto",
            "num_predictions": 1,
            "avg_retrieved_count": 1.0,
            "avg_evidence_item_count": 1.0,
            "avg_gold_document_hit": 1.0,
            "avg_gold_page_hit": 1.0,
            "avg_gold_span_hit": 1.0,
            "avg_answer_nonempty_after_cleaning": 1.0,
        }
    ]
    assert report["summary"]["route_confusion_table"] == [
        {
            "dataset_name": "qasper",
            "route": "controller_auto",
            "recommended_route": "doc_text",
            "selected_route": "doc_text",
            "count": 1,
        }
    ]
    assert report["summary"]["diagnostic_failure_counts"] == [
        {
            "dataset_name": "qasper",
            "route": "controller_auto",
            "failure_class": "none",
            "retrieval_failure_type": "none",
            "citation_failure_type": "none",
            "count": 1,
        }
    ]


def test_prediction_diagnostics_classifies_raw_retriever_zero():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 0}],
            "gold_pages": [3],
            "predicted_pages": [],
            "predicted_sources": [],
            "gold_sources": ["doc#page:3"],
            "gold_evidence": [{"citation": "doc#page:3", "page": 3}],
            "predicted_answer": "",
        }
    )

    assert diagnostics["retrieval_failure_type"] == "raw_retriever_zero"
    assert diagnostics["citation_failure_type"] == "missing_citation_metadata"
    assert diagnostics["failure_class"] == "no_retrieved_hits"


def test_prediction_diagnostics_classifies_runtime_error_before_retrieval():
    diagnostics = prediction_diagnostics(
        {
            "error": (
                "Error code: 400 - maximum context length is 4096 tokens, "
                "but the prompt contains 4097 input tokens."
            ),
            "retrieved_hits": [],
            "retrieval_trace": [],
            "gold_pages": [77],
            "predicted_pages": [],
            "predicted_sources": [],
            "gold_sources": ["doc#page:77"],
            "gold_evidence": [{"citation": "doc#page:77", "page": 77}],
            "predicted_answer": "",
        }
    )

    assert diagnostics["retrieval_failure_type"] == "execution_error"
    assert diagnostics["citation_failure_type"] == "not_evaluated_execution_error"
    assert diagnostics["failure_class"] == "execution_error"


def test_prediction_diagnostics_classifies_wrong_page_after_retrieval():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "page_label": "9",
                    "source": "doc#page:9",
                    "text": "Wrong page.",
                }
            ],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 5}],
            "gold_pages": [3],
            "predicted_pages": [9],
            "predicted_sources": ["doc#page:9"],
            "gold_sources": ["doc#page:3"],
            "gold_evidence": [{"citation": "doc#page:3", "page": 3}],
            "predicted_answer": "Wrong page.",
        }
    )

    assert diagnostics["retrieval_failure_type"] == "wrong_page"
    assert diagnostics["citation_failure_type"] == "citation_miss"
    assert diagnostics["failure_class"] == "wrong_locator"


def test_prediction_diagnostics_accepts_parser_page_aligned_by_visual_quote():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "59",
                    "source_backrefs": ["doc#page:59"],
                    "text": (
                        "Zone Americas (AMS). Zone AMS in millions of CHF. "
                        "Sales 2020 34.0 billion. Organic growth 4.8%, real "
                        "internal growth 4.1%. United States and Canada, "
                        "Latin America and Caribbean."
                    ),
                }
            ],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 5}],
            "gold_pages": [58],
            "predicted_pages": [59],
            "predicted_sources": ["doc#page:59"],
            "gold_sources": ["doc#page:58"],
            "gold_evidence": [
                {
                    "document_id": "doc",
                    "citation": "doc#page:58",
                    "page": 58,
                    "element_type": "table",
                    "image_quote": (
                        "The Zone AMS table reports sales of CHF 34.0 billion, "
                        "organic growth of 4.8%, real internal growth of 4.1%, "
                        "and sales for United States and Canada and Latin "
                        "America and Caribbean."
                    ),
                }
            ],
            "predicted_answer": "Zone AMS sales were CHF 34.0 billion.",
        }
    )

    assert diagnostics["gold_page_hit"] == 1.0
    assert diagnostics["retrieval_failure_type"] == "none"
    assert diagnostics["citation_failure_type"] == "none"
    assert diagnostics["failure_class"] == "none"


def test_prediction_diagnostics_accepts_source_citation_when_gold_span_is_retrieved():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [
                {
                    "document_id": "paper-1",
                    "source_id": "paper-1",
                    "text": "The proposed method improves recall.",
                    "source_backrefs": ["paper-1#source"],
                }
            ],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 1}],
            "gold_pages": [],
            "predicted_pages": [],
            "predicted_sources": ["paper-1#source"],
            "gold_sources": [],
            "gold_evidence": [
                {
                    "document_id": "paper-1",
                    "citation": "paper-1#evidence:1",
                    "span": "The proposed method improves recall.",
                }
            ],
            "predicted_answer": "The proposed method improves recall.",
        }
    )

    assert diagnostics["retrieval_failure_type"] == "none"
    assert diagnostics["citation_failure_type"] == "none"
    assert diagnostics["failure_class"] == "none"


def test_prediction_diagnostics_classifies_wrong_source_without_page_gold():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [
                {
                    "document_id": "paper-2",
                    "source_id": "paper-2",
                    "text": "Wrong source text.",
                }
            ],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 1}],
            "gold_pages": [],
            "predicted_pages": [],
            "predicted_sources": ["paper-2#source"],
            "gold_sources": [],
            "gold_evidence": [
                {
                    "document_id": "paper-1",
                    "citation": "paper-1#evidence:1",
                    "span": "The proposed method improves recall.",
                }
            ],
            "predicted_answer": "Wrong source text.",
        }
    )

    assert diagnostics["gold_document_hit"] == 0.0
    assert diagnostics["retrieval_failure_type"] == "wrong_source"
    assert diagnostics["failure_class"] == "wrong_source"


def test_prediction_diagnostics_classifies_missing_gold_span_after_source_hit():
    diagnostics = prediction_diagnostics(
        {
            "retrieved_hits": [
                {
                    "document_id": "paper-1",
                    "source_id": "paper-1",
                    "text": "Same paper but unrelated paragraph.",
                }
            ],
            "retrieval_trace": [{"stage": "raw_retriever", "count": 1}],
            "gold_pages": [],
            "predicted_pages": [],
            "predicted_sources": ["paper-1#source"],
            "gold_sources": [],
            "gold_evidence": [
                {
                    "document_id": "paper-1",
                    "citation": "paper-1#evidence:1",
                    "span": "The proposed method improves recall.",
                }
            ],
            "predicted_answer": "Same paper but unrelated paragraph.",
        }
    )

    assert diagnostics["gold_document_hit"] == 1.0
    assert diagnostics["gold_span_hit"] == 0.0
    assert diagnostics["retrieval_failure_type"] == "gold_span_missing"
    assert diagnostics["failure_class"] == "gold_span_missing"


def _write_diagnostic_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("Revenue increased in 2026.", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "controller_auto",
                        "engine": "docqa_runtime",
                        "route_policy": "auto",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What happened to revenue?",
                        "answers": ["Revenue increased in 2026."],
                        "gold_evidence": [
                            {
                                "document_id": "doc",
                                "page": 2,
                                "span": "Revenue increased in 2026.",
                                "citation": "doc#page:2",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path
