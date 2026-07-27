from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer


def test_finalizer_cites_executed_finance_evidence_not_first_candidate():
    prediction: dict[str, Any] = {
        "predicted_answer": "$5,818.0 million$5,818.0 million",
        "answer_type": "numeric",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "unrelated-first-hit",
                    "source_id": "runtime-file-id",
                    "page_label": "105",
                    "text": "Unrelated retrieved evidence.",
                },
                {
                    "evidence_id": "working-capital-table",
                    "source_id": "runtime-file-id",
                    "page_label": "30",
                    "text": (
                        "Total current assets 19,815. "
                        "Total current liabilities 13,997."
                    ),
                },
            ],
            "metadata": {
                "finance_numeric_trace": {
                    "calculation_execution": {
                        "status": "ok",
                        "citation_ids": ["working-capital-table"],
                    }
                }
            },
        },
        "predicted_sources": [
            "LOCKHEEDMARTIN_2021_10K#page:105",
            "LOCKHEEDMARTIN_2021_10K#page:30",
        ],
        "gold_evidence": [{"source_id": "LOCKHEEDMARTIN_2021_10K", "page_label": "68"}],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench_plan5_text_main_current",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == "$5,818.0 million"
    assert prediction["answer_for_user"] == (
        "$5,818.0 million LOCKHEEDMARTIN_2021_10K#page:30"
    )
    assert prediction["predicted_citations"] == ["LOCKHEEDMARTIN_2021_10K#page:30"]
