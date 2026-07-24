from typing import Any

from benchmark.stage_metrics import (
    prediction_stage_metric_status,
    prediction_stage_metrics,
    stage_metric_summary,
)


def test_stage_metrics_report_retrieval_pages_dedup_slots_and_calculation():
    prediction = {
        "gold_pages": [2, 3],
        "gold_evidence": [
            {"source_id": "report", "page": 2, "element_id": "cell-a"},
            {"source_id": "report", "page": 3, "element_id": "cell-b"},
        ],
        "predicted_pages": [2, 3],
        "predicted_element_ids": ["cell-a", "cell-b"],
        "evidence_metadata": {
            "candidate_evidence": [
                {"source_id": "report", "page_label": "2", "element_id": "cell-a"},
                {"source_id": "other", "page_label": "9"},
                {"source_id": "report", "page_label": "3", "element_id": "cell-b"},
            ],
            "reranked_evidence": [
                {"source_id": "report", "page_label": "3", "element_id": "cell-b"},
                {"source_id": "report", "page_label": "2", "element_id": "cell-a"},
            ],
            "slot_coverage": 1.0,
            "dedupe_trace": {"duplicate_ratio": 0.25},
            "evidence_selection_trace": {"unique_pages": 2},
            "finance_numeric_trace": {
                "calculation_plan": {
                    "operands": [{"operand_id": "a"}, {"operand_id": "b"}],
                    "steps": [{"step_id": "result", "operator": "ratio"}],
                },
                "calculation_verification": {
                    "valid": True,
                    "verified_operand_ids": ["a", "b"],
                    "errors": [],
                },
                "calculation_execution": {"status": "ok"},
            },
        },
        "semantic_answer_evaluation": {"judge_status": "ok"},
        "answer_for_scoring": "4.5",
        "answer_finalization": {"repetition_removed": True},
        "controller_trace": [
            {
                "stage": "claim_aggregation",
                "input_claim_count": 3,
                "output_claim_count": 2,
            }
        ],
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["candidate_recall_at_50"] == 1.0
    assert metrics["reranked_recall_at_10"] == 1.0
    assert metrics["retrieval_mrr"] == 1.0
    assert metrics["retrieval_ndcg"] is not None
    assert metrics["retrieval_ndcg"] > 0.9
    assert metrics["all_gold_pages_hit"] == 1.0
    assert metrics["gold_table_cell_recall"] == 1.0
    assert metrics["slot_coverage"] == 1.0
    assert metrics["unique_pages"] == 2.0
    assert metrics["duplicate_ratio"] == 0.25
    assert metrics["operand_accuracy"] == 1.0
    assert metrics["all_operands_bound"] == 1.0
    assert metrics["executor_activation_rate"] == 1.0
    assert metrics["program_accuracy"] == 1.0
    assert metrics["execution_accuracy"] == 1.0
    assert metrics["unit_accuracy"] == 1.0
    assert metrics["claim_duplicate_rate"] == 1 / 3
    assert metrics["final_answer_duplicate_rate"] == 0.0
    assert metrics["final_answer_repetition_repair_rate"] == 1.0
    assert metrics["judge_failure_rate"] == 0.0
    assert (
        prediction_stage_metric_status(prediction)["calculation_pipeline"][
            "failure_stage"
        ]
        == "none"
    )


def test_finance_stage_metrics_expose_missing_executor_activation():
    prediction = {
        "dataset_name": "financebench",
        "answer_type": "numeric",
        "evidence_metadata": {},
    }

    metrics = prediction_stage_metrics(prediction)
    status = prediction_stage_metric_status(prediction)

    assert metrics["executor_activation_rate"] == 0.0
    assert metrics["all_operands_bound"] == 0.0
    assert status["calculation_pipeline"] == {
        "status": "measured",
        "failure_stage": "retrieval_or_plan",
    }


def test_finance_stage_metrics_read_numeric_applicability_from_query_plan():
    prediction = {
        "evidence_metadata": {
            "query_plan": {
                "answer_type": "numeric",
                "constraints": {"verification_domain": "finance"},
            }
        }
    }

    metrics = prediction_stage_metrics(prediction)
    status = prediction_stage_metric_status(prediction)

    assert metrics["executor_activation_rate"] == 0.0
    assert metrics["all_operands_bound"] == 0.0
    assert status["calculation_pipeline"] == {
        "status": "measured",
        "failure_stage": "retrieval_or_plan",
    }


def test_finance_stage_metrics_do_not_measure_long_form_query_plan_as_numeric():
    prediction = {
        "dataset_name": "financebench",
        "answer_type": "long_form",
        "evidence_metadata": {
            "query_plan": {
                "answer_type": "long_form",
                "constraints": {"verification_domain": "finance"},
            }
        },
    }

    metrics = prediction_stage_metrics(prediction)
    status = prediction_stage_metric_status(prediction)

    assert metrics["executor_activation_rate"] is None
    assert metrics["all_operands_bound"] is None
    assert status["calculation_pipeline"] == {
        "status": "not_applicable",
        "failure_stage": "not_applicable",
    }


def test_stage_metric_summary_preserves_null_when_trace_is_unavailable():
    prediction: dict[str, Any] = {"stage_metrics": prediction_stage_metrics({})}
    prediction["stage_metric_status"] = prediction_stage_metric_status(prediction)
    predictions = [prediction]

    summary = stage_metric_summary(predictions)

    assert summary["avg_candidate_recall_at_50"] is None
    assert summary["coverage_candidate_recall_at_50"] == 0.0
    assert summary["avg_final_answer_duplicate_rate"] is None
    assert summary["avg_judge_failure_rate"] is None


def test_retrieval_metrics_distinguish_missing_trace_from_measured_empty_result():
    base = {
        "gold_pages": [2],
        "gold_evidence": [{"document_id": "report", "page": 2}],
    }
    missing_trace = dict(base)
    empty_trace = {
        **base,
        "evidence_metadata": {
            "candidate_evidence": [],
            "reranked_evidence": [],
        },
    }

    missing_metrics = prediction_stage_metrics(missing_trace)
    empty_metrics = prediction_stage_metrics(empty_trace)
    missing_status = prediction_stage_metric_status(missing_trace)
    empty_status = prediction_stage_metric_status(empty_trace)

    assert missing_metrics["candidate_recall_at_50"] is None
    assert missing_status["candidate_recall_at_50"]["status"] == "unavailable"
    assert empty_metrics["candidate_recall_at_50"] == 0.0
    assert empty_metrics["reranked_recall_at_10"] == 0.0
    assert empty_status["candidate_recall_at_50"]["status"] == "measured"


def test_candidate_page_recall_does_not_require_matching_gold_element_id():
    prediction = {
        "gold_pages": [4],
        "gold_evidence": [
            {
                "document_id": "P18-1041",
                "page": 4,
                "element_id": "image5",
            }
        ],
        "predicted_element_ids": [],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "source_id": "runtime-uuid",
                    "source_name": "P18-1041.pdf",
                    "page_label": "4",
                    "element_id": "",
                }
            ],
            "reranked_evidence": [
                {
                    "source_id": "runtime-uuid",
                    "source_name": "P18-1041.pdf",
                    "page_label": "4",
                    "element_id": "",
                }
            ],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["candidate_recall_at_50"] == 1.0
    assert metrics["reranked_recall_at_10"] == 1.0
    assert metrics["gold_table_cell_recall"] == 0.0


def test_retrieval_ndcg_counts_each_gold_identity_only_once():
    prediction = {
        "gold_pages": [4],
        "gold_evidence": [{"document_id": "report", "page": 4}],
        "evidence_metadata": {
            "candidate_evidence": [
                {"source_id": "report", "page_label": "4", "evidence_id": "a"},
                {"source_id": "report", "page_label": "4", "evidence_id": "b"},
                {"source_id": "report", "page_label": "4", "evidence_id": "c"},
            ],
            "reranked_evidence": [
                {"source_id": "report", "page_label": "4", "evidence_id": "a"},
                {"source_id": "report", "page_label": "4", "evidence_id": "b"},
                {"source_id": "report", "page_label": "4", "evidence_id": "c"},
            ],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["retrieval_ndcg"] == 1.0
