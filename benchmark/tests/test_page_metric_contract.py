from __future__ import annotations

from benchmark.scoring import score_prediction


def test_canonical_mapped_page_does_not_count_as_strict_gold_page():
    prediction = {
        "predicted_answer": "65.4%",
        "gold_answers": ["65.4%"],
        "predicted_pages": [62],
        "gold_pages": [62],
        "predicted_sources": ["adobe#page:62"],
        "gold_sources": ["adobe#page:62"],
        "gold_evidence": [
            {
                "source_id": "adobe",
                "dataset_page": 61,
                "page": 62,
                "span": "Operating income increased by 65.4 percent.",
                "page_mapping": {
                    "dataset_page": 61,
                    "runtime_page": 62,
                    "mapping_source": "financebench_manifest_alignment",
                    "mapping_confidence": 1.0,
                    "mapping_version": "financebench_page_mapping.v1",
                },
            }
        ],
        "evidence_bundle": {
            "items": [
                {
                    "source_id": "adobe",
                    "page_label": "62",
                    "text": "Operating income increased by 65.4 percent.",
                }
            ]
        },
        "retrieved_hits": [],
    }

    metrics = score_prediction(prediction)

    assert metrics["strict_gold_page_coverage"] == 0.0
    assert metrics["canonical_mapped_page_coverage"] == 1.0
    assert metrics["equivalent_evidence_page_coverage"] == 1.0
    assert prediction["page_mapping_trace"] == [
        {
            "dataset_page": "61",
            "runtime_page": "62",
            "mapping_source": "financebench_manifest_alignment",
            "mapping_confidence": 1.0,
            "mapping_version": "financebench_page_mapping.v1",
        }
    ]


def test_equivalent_evidence_page_is_not_strict_or_canonical_hit():
    prediction = {
        "predicted_answer": "answer",
        "gold_answers": ["answer"],
        "predicted_pages": [63],
        "gold_pages": [62],
        "predicted_sources": ["adobe#page:63"],
        "gold_sources": ["adobe#page:62"],
        "gold_evidence": [
            {
                "source_id": "adobe",
                "dataset_page": 61,
                "page": 62,
                "span": "The operating income value was 100 million.",
            }
        ],
        "evidence_bundle": {
            "items": [
                {
                    "source_id": "adobe",
                    "page_label": "63",
                    "text": "The operating income value was 100 million.",
                }
            ]
        },
        "retrieved_hits": [],
    }

    metrics = score_prediction(prediction)

    assert metrics["strict_gold_page_coverage"] == 0.0
    assert metrics["canonical_mapped_page_coverage"] == 0.0
    assert metrics["equivalent_evidence_page_coverage"] == 1.0
