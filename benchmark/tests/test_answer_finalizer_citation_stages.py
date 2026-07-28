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


def test_atomic_cell_citation_does_not_expand_to_sibling_cells():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {
                "answer": "Revenue was 12 million.",
                "citations": [
                    {
                        "evidence_id": "table-1",
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
                    "evidence_id": "table-1",
                    "source_id": "report",
                    "page_label": "5",
                    "cell_id": "revenue-2022",
                    "evidence_level": "cell",
                    "text": "Revenue 2022 10 million.",
                },
                {
                    "evidence_id": "table-1",
                    "source_id": "report",
                    "page_label": "5",
                    "cell_id": "revenue-2023",
                    "evidence_level": "cell",
                    "text": "Revenue 2023 12 million.",
                },
            ],
            "metadata": {},
        },
        "evidence_metadata": {},
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == []


def test_citation_source_page_pair_cannot_cross_join():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {
                "answer": "The documents jointly report growth.",
                "citations": [{"source_id": "document-a", "page_label": "2"}],
            }
        ),
        "answer_type": "citation_qa",
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "graph-aggregate",
                    "source_id": "graph",
                    "source_backrefs": [
                        "document-a#page:1",
                        "document-b#page:2",
                    ],
                    "text": "A cross-document aggregate.",
                }
            ],
            "metadata": {},
        },
        "evidence_metadata": {},
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == []
