import json

from benchmark.reports import write_reports
from benchmark.stage_metrics import prediction_stage_metrics


def test_compact_artifact_preserves_complete_candidate_identity_lineage(tmp_path):
    candidates = [
        {
            "evidence_id": f"candidate-{page}",
            "canonical_id": f"report#page:{page}",
            "source_id": "runtime-report",
            "source_name": "report.pdf",
            "page_label": str(page),
            "cell_id": f"table#row:metric#column:{page}",
            "row_label": "Metric",
            "column_label": str(page),
            "source_backrefs": [f"runtime-report#page:{page}"],
            "text": "x" * 10_000,
            "metadata": {"reranking_score": 1.0 / page},
        }
        for page in range(1, 61)
    ]
    candidates[-1][
        "text"
    ] = "The audited table reports current assets of 20,991 million in 2021."
    report = {
        "summary": {
            "suite_name": "Candidate Identity Compact Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "gold_evidence": [
                    {
                        "document_id": "report",
                        "page": 60,
                        "span": (
                            "The audited table reports current assets of "
                            "20,991 million in 2021."
                        ),
                    }
                ],
                "stage_metrics": {"gold_evidence_support_recall": 1.0},
                "evidence_metadata": {
                    "candidate_evidence": candidates,
                    "reranked_evidence": [candidates[-1]],
                },
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Candidate Identity Compact Suite")
    prediction = _read_jsonl(run_dir / "predictions.jsonl")[0]
    compact_candidates = prediction["evidence_metadata"]["candidate_evidence"]

    assert len(compact_candidates) == 60
    assert compact_candidates[-1] == {
        "evidence_id": "candidate-60",
        "canonical_id": "report#page:60",
        "source_id": "runtime-report",
        "source_name": "report.pdf",
        "page_label": "60",
        "cell_id": "table#row:metric#column:60",
        "row_label": "Metric",
        "column_label": "60",
        "source_backrefs": ["runtime-report#page:60"],
        "identity_projection": "evidence_identity_projection.v1",
    }
    metrics = prediction_stage_metrics(prediction)
    assert metrics["candidate_recall_at_50"] == 0.0
    assert metrics["candidate_pool_recall_at_80"] == 1.0
    assert metrics["reranked_recall_at_10"] == 1.0
    assert metrics["reranker_lineage_coverage"] == 1.0
    assert metrics["gold_evidence_support_recall"] == 1.0


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
