from benchmark.stage_metrics import prediction_stage_metrics, stage_metric_summary


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
    assert metrics["program_accuracy"] == 1.0
    assert metrics["execution_accuracy"] == 1.0
    assert metrics["unit_accuracy"] == 1.0
    assert metrics["claim_duplicate_rate"] == 1 / 3
    assert metrics["judge_failure_rate"] == 0.0


def test_stage_metric_summary_preserves_null_when_trace_is_unavailable():
    predictions = [{"stage_metrics": prediction_stage_metrics({})}]

    summary = stage_metric_summary(predictions)

    assert summary["avg_candidate_recall_at_50"] is None
    assert summary["avg_judge_failure_rate"] is None
