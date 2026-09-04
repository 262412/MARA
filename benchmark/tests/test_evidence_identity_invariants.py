from benchmark.stage_metrics import (
    prediction_stage_metric_status,
    prediction_stage_metrics,
)


def _candidate(index: int) -> dict[str, object]:
    return {
        "canonical_id": f"candidate-{index}",
        "source_id": "report",
        "page_label": str(index),
        "text": f"candidate text {index}",
    }


def test_reranked_recall_uses_the_full_canonical_candidate_pool_lineage():
    candidates = [_candidate(index) for index in range(1, 61)]
    prediction = {
        "gold_evidence": [{"source_id": "report", "page": 60}],
        "evidence_metadata": {
            "candidate_evidence": candidates,
            "reranked_evidence": [candidates[-1]],
        },
    }

    metrics = prediction_stage_metrics(prediction)
    status = prediction_stage_metric_status(prediction)

    assert metrics["candidate_recall_at_50"] == 0.0
    assert metrics["candidate_pool_recall_at_80"] == 1.0
    assert metrics["reranked_recall_at_10"] == 1.0
    assert metrics["reranker_lineage_coverage"] == 1.0
    assert status["reranker_lineage_coverage"]["violation_count"] == 0


def test_reranker_lineage_reports_items_that_never_entered_candidate_pool():
    prediction = {
        "gold_evidence": [{"source_id": "report", "page": 2}],
        "evidence_metadata": {
            "candidate_evidence": [_candidate(1)],
            "reranked_evidence": [_candidate(2)],
        },
    }

    metrics = prediction_stage_metrics(prediction)
    status = prediction_stage_metric_status(prediction)

    assert metrics["reranker_lineage_coverage"] == 0.0
    assert status["reranker_lineage_coverage"] == {
        "status": "measured",
        "candidate_pool_count": 1,
        "reranked_count": 1,
        "violation_count": 1,
    }


def test_reranker_lineage_rejects_global_text_only_match():
    prediction = {
        "gold_evidence": [],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "evidence_id": "candidate",
                    "source_id": "document-a",
                    "page_label": "2",
                    "text": "The same boilerplate sentence.",
                }
            ],
            "reranked_evidence": [
                {
                    "evidence_id": "injected",
                    "source_id": "document-b",
                    "page_label": "8",
                    "text": "The same boilerplate sentence.",
                }
            ],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["reranker_lineage_coverage"] == 0.0


def test_reranker_lineage_rejects_shared_parent_alias():
    prediction = {
        "gold_evidence": [],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "evidence_id": "table-1",
                    "source_id": "report",
                    "page_label": "5",
                    "cell_id": "revenue-2022",
                    "evidence_level": "cell",
                    "text": "Revenue 2022 10 million.",
                }
            ],
            "reranked_evidence": [
                {
                    "evidence_id": "table-1",
                    "source_id": "report",
                    "page_label": "5",
                    "cell_id": "net-income-2023",
                    "evidence_level": "cell",
                    "text": "Net income 2023 4 million.",
                }
            ],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["reranker_lineage_coverage"] == 0.0


def test_equivalent_fact_support_does_not_redefine_strict_gold_page_hit():
    table_text = (
        "Consolidated balance sheet current assets 20,991 current liabilities "
        "15,173 total assets 50,873 total liabilities 43,798 common stock "
        "shareholders equity 7,075 dollars in millions 2021."
    )
    prediction = {
        "gold_pages": [68],
        "gold_evidence": [
            {
                "source_id": "LOCKHEEDMARTIN_2021_10K",
                "page": 68,
                "span": table_text,
            }
        ],
        "predicted_pages": [30],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "source_name": "/reports/LOCKHEEDMARTIN_2021_10K.pdf",
                    "page_label": "30",
                    "text": table_text,
                }
            ],
            "reranked_evidence": [],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["all_gold_pages_hit"] == 0.0
    assert metrics["candidate_recall_at_50"] == 0.0
    assert metrics["gold_evidence_support_recall"] == 1.0
