from benchmark.dataset_decision_protocol import (
    phase2_dataset_decision,
    phase2_failure_counts,
    phase2_failure_type,
)
from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig
from benchmark.summary import add_mara_summary_fields


def test_phase2_dataset_decision_freezes_main_and_blocked_candidates():
    qasper = phase2_dataset_decision("qasper_plan5_text_main_current")
    slidevqa = phase2_dataset_decision("slidevqa_test_shard0_multimodal")
    vidore = phase2_dataset_decision("vidore_docvqa_test_visual_retriever")

    assert qasper["decision"] == "main_quality_candidate"
    assert qasper["headline_routes"] == ["text_rag"]
    assert qasper["benchmark_prompt_policy"] == "gold_answer_v1"
    assert qasper["benchmark_no_think"] is True

    assert slidevqa["decision"] == "blocked_visual_candidate"
    assert slidevqa["blocked_routes"] == ["page_image_rag_vlm"]
    assert "requires_vlm_backend" in slidevqa["blockers"]

    assert vidore["decision"] == "retrieval_diagnostic"
    assert vidore["diagnostic_routes"] == [
        "colqwen_retriever_only",
        "colpali_retriever_only",
    ]
    assert "missing_full_qa_generation_route" in vidore["blockers"]


def test_phase2_failure_type_splits_abstention_and_retriever_only_gaps():
    route_timeout = {
        "route": "controller_auto",
        "error": "Route controller_auto timed out after 120.0 seconds.",
        "error_type": "route_timeout",
    }
    finance_abstention = {
        "route": "text_rag",
        "retrieved_hits": [{"text": "wrong finance paragraph"}],
        "metrics": {"abstained": 1.0, "false_abstention": 1.0},
        "diagnostics": {"retrieved_count": 1, "failure_class": "gold_span_missing"},
    }
    slide_abstention = {
        "route": "text_rag",
        "retrieved_hits": [],
        "metrics": {"abstained": 1.0, "false_abstention": 1.0},
        "diagnostics": {"retrieved_count": 0, "failure_class": "no_retrieved_hits"},
    }
    vidore_retriever_only = {
        "route": "colqwen_retriever_only",
        "predicted_answer": "MARA found visual page evidence, but no VLM backend is configured.",
        "metrics": {"page_hit": 1.0, "citation_recall": 1.0},
        "diagnostics": {"failure_class": "none"},
    }

    assert phase2_failure_type(route_timeout) == "route_timeout"
    assert phase2_failure_type(finance_abstention) == (
        "false_abstention_after_retrieval"
    )
    assert phase2_failure_type(slide_abstention) == "false_abstention_no_evidence"
    assert phase2_failure_type(vidore_retriever_only) == (
        "retrieval_diagnostic_no_generation"
    )


def test_phase2_failure_counts_groups_predictions_by_phase2_type():
    rows = phase2_failure_counts(
        "financebench_plan5_text_main_current",
        [
            {
                "route": "text_rag",
                "retrieved_hits": [{"text": "wrong paragraph"}],
                "metrics": {"abstained": 1.0, "false_abstention": 1.0},
                "diagnostics": {
                    "retrieved_count": 1,
                    "failure_class": "gold_span_missing",
                },
            },
            {
                "route": "text_rag",
                "retrieved_hits": [{"text": "calculation source"}],
                "metrics": {"f1": 0.0, "abstained": 0.0},
                "diagnostics": {"retrieved_count": 1, "failure_class": "none"},
            },
        ],
    )

    assert rows == [
        {
            "dataset_name": "financebench_plan5_text_main_current",
            "dataset_decision": "diagnostic_followup",
            "route": "text_rag",
            "phase2_failure_type": "false_abstention_after_retrieval",
            "count": 1,
        },
        {
            "dataset_name": "financebench_plan5_text_main_current",
            "dataset_decision": "diagnostic_followup",
            "route": "text_rag",
            "phase2_failure_type": "answer_mismatch_after_retrieval",
            "count": 1,
        },
    ]


def test_run_benchmark_summary_includes_phase2_protocol(monkeypatch, tmp_path):
    class Engine:
        @staticmethod
        def run_example(_bundle, example):
            return {
                "example_id": example.example_id,
                "document_id": example.document_id,
                "question": example.question,
                "gold_answers": example.answers,
                "gold_pages": [],
                "gold_sources": [],
                "predicted_answer": "wrong answer",
                "predicted_pages": [],
                "predicted_sources": ["doc#source"],
                "retrieved_hits": [
                    {
                        "document_id": "doc",
                        "source_backrefs": ["doc#source"],
                        "text": "right answer",
                    }
                ],
                "evidence_bundle": {},
            }

        @staticmethod
        def document_reports():
            return []

    manifest_path = tmp_path / "manifest.json"
    (tmp_path / "doc.txt").write_text("source text", encoding="utf-8")
    manifest_path.write_text(
        """
        {
          "schema_version": 2,
          "dataset_name": "qasper_plan5_text_main_current",
          "documents": [{"document_id": "doc", "path": "doc.txt"}],
              "examples": [
                {
                  "example_id": "ex",
                  "document_id": "doc",
                  "question": "What is the answer?",
                  "answers": ["right answer"],
                  "gold_evidence": [
                    {
                      "document_id": "doc",
                      "span": "right answer",
                      "citation": "doc#source"
                    }
                  ]
                }
              ],
          "routes": [{"route_id": "text_rag", "engine": "docqa_runtime"}]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda _engine_name, _config: Engine(),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(suite_name="phase2", output_dir=tmp_path / "out"),
    )

    assert report["summary"]["phase2_dataset_decision"]["decision"] == (
        "main_quality_candidate"
    )
    assert report["summary"]["phase2_failure_counts"] == [
        {
            "dataset_name": "qasper_plan5_text_main_current",
            "dataset_decision": "main_quality_candidate",
            "route": "text_rag",
            "phase2_failure_type": "answer_mismatch_after_retrieval",
            "count": 1,
        }
    ]


def test_rescored_summary_includes_phase2_protocol_fields():
    rescored = add_mara_summary_fields(
        {"dataset_name": "slidevqa_test_shard0_multimodal"},
        [
            {
                "route": "text_rag",
                "retrieved_hits": [],
                "metrics": {"abstained": 1.0, "false_abstention": 1.0},
                "diagnostics": {
                    "retrieved_count": 0,
                    "failure_class": "no_retrieved_hits",
                },
                "performance": {},
            }
        ],
    )

    assert rescored["phase2_dataset_decision"]["decision"] == (
        "blocked_visual_candidate"
    )
    assert rescored["phase2_failure_counts"] == [
        {
            "dataset_name": "slidevqa_test_shard0_multimodal",
            "dataset_decision": "blocked_visual_candidate",
            "route": "text_rag",
            "phase2_failure_type": "false_abstention_no_evidence",
            "count": 1,
        }
    ]
