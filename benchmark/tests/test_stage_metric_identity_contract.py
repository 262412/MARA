from benchmark.stage_metrics import prediction_stage_metrics


def test_all_gold_pages_hit_uses_source_page_pairs():
    prediction = {
        "gold_pages": [5],
        "gold_evidence": [{"source_id": "document-a", "page_label": "5"}],
        "predicted_pages": [5],
        "predicted_sources": ["document-b"],
        "evidence_metadata": {
            "selected_evidence": [
                {"source_id": "document-b", "page_label": "5"}
            ]
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["all_gold_pages_hit"] == 0.0
    assert metrics["legacy_page_only_all_gold_pages_hit"] == 1.0


def test_identity_only_gold_requirement_reads_nested_local_id():
    prediction = {
        "gold_evidence_requirements": [
            {
                "requirement_id": "span:support",
                "acceptable_evidence": [
                    {
                        "identity": {
                            "source_id": "paper",
                            "kind": "span",
                            "local_id": "supporting-span",
                        }
                    }
                ],
            }
        ],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "source_id": "paper",
                    "span_id": "supporting-span",
                    "evidence_level": "span",
                }
            ]
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["candidate_recall_at_50"] == 1.0
