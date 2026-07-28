import json
from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer


def test_cited_evidence_comes_from_emitted_citations():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {
                "answer": "Revenue increased.",
                "citations": [
                    {
                        "evidence_id": "revenue-evidence",
                        "source_id": "report",
                        "page_label": "5",
                    }
                ],
            }
        ),
        "answer_type": "citation_qa",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "appendix-evidence",
                    "source_id": "report",
                    "page_label": "4",
                    "text": "An unrelated appendix.",
                },
                {
                    "evidence_id": "revenue-evidence",
                    "source_id": "report",
                    "page_label": "5",
                    "text": "Revenue increased.",
                },
            ],
            "metadata": {
                "verified_evidence": [
                    {
                        "evidence_id": "appendix-evidence",
                        "source_id": "report",
                        "page_label": "4",
                    },
                    {
                        "evidence_id": "revenue-evidence",
                        "source_id": "report",
                        "page_label": "5",
                    },
                ]
            },
        },
        "evidence_metadata": {},
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    for metadata in (
        prediction["evidence_bundle"]["metadata"],
        prediction["evidence_metadata"],
    ):
        assert [
            item["evidence_id"] for item in metadata["emitted_citation_evidence"]
        ] == ["revenue-evidence"]
        assert metadata["cited_evidence"] == metadata["emitted_citation_evidence"]
