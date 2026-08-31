import json
from pathlib import Path
from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.citation_stage_projection import _resolve_frozen_premises
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows
from benchmark.tests.qasper_natural_semantic_pack_fixture import row as natural_row
from ktem.docqa.evidence_identity import identity_of


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


def test_verified_frozen_plan_premises_reach_emitted_citation_evidence():
    prediction = natural_row()
    metadata = prediction["evidence_metadata"]
    plan = metadata["qasper_canonical_semantic_pack"]["proposition_binding"][
        "canonical_evidence_plan"
    ]["support_plan"]
    metadata["semantic_proposition_authority"] = {
        "contract_id": "semantic_proposition_verdict.v4",
        "status": "verified",
        "reason": "semantic_evidence_set_bound",
        "premise_count": len(plan["span_refs"]),
        "canonical_evidence_plan_id": plan["plan_id"],
        "canonical_plan_digest": plan["plan_id"],
    }
    prediction["answer_type"] = "boolean"
    prediction["predicted_answer"] = "yes"
    prediction["answer_for_user"] = "yes"
    prediction.pop("gold_evidence", None)

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper",
        mode="scoring_adapter_v1",
    )

    expected_id = "evidence:paper:natural-probe-evidence"
    assert [
        identity_of(item).key for item in metadata["emitted_citation_evidence"]
    ] == [expected_id]
    assert prediction["structured_citations"][0]["evidence_id"] == expected_id
    assert prediction["predicted_citations"] == ["paper#source"]
    assert metadata["citation_stage_trace"]["projection_source"] == (
        "frozen_canonical_plan"
    )
    [debug_row] = qasper_semantic_debug_rows([prediction])
    assert debug_row["citation_stage_trace"]["status"] == "emitted"
    assert debug_row["frozen_citation_projection_trace"]["status"] == "verified"
    assert debug_row["citation_projection_source"] == "frozen_canonical_plan"
    assert debug_row["emitted_citation_evidence_identities"] == [expected_id]


def test_two_frozen_spans_on_one_real_record_emit_one_citation_record():
    fixture_path = (
        Path(__file__).parents[2]
        / "libs/ktem/ktem_tests/fixtures/qasper_10389151_semantic_defects.json"
    )
    case = json.loads(fixture_path.read_text(encoding="utf-8"))["cases"][
        "6568a31241167f618ef5ede939053feaa2fb0d7e"
    ]
    candidate = {
        "evidence_id": case["evidence_id"],
        "source_id": case["document_id"],
        "text": " ".join(selector["text"] for selector in case["selectors"]),
    }
    premises = [
        {
            "evidence_id": selector["evidence_id"],
            "span_selector": selector["selector_id"],
        }
        for selector in case["selectors"]
    ]

    resolved, reason = _resolve_frozen_premises(premises, [candidate])

    assert reason == ""
    assert len(premises) == 2
    assert [identity_of(item).key for item in resolved] == [identity_of(candidate).key]
