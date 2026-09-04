from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import _initial_evidence_items, build_evidence_bundle
from ktem.docqa.evidence_identity import (
    EvidenceIdentityConflictError,
    canonicalize_and_dedupe_evidence,
    identity_of,
)
from ktem.docqa.evidence_text import evidence_text
from ktem.docqa.graph_evidence import _graph_locator_items
from ktem.docqa.hybrid_fusion import _retriever_rank_lists
from ktem.docqa.query_plan_schema import EvidenceSlot
from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    score_evidence_for_slot,
)
from ktem.docqa.verification import verify_decision


def _retrieve_decision():
    return SimpleNamespace(status="good", retry=False)


def test_derived_numeric_claim_uses_calculation_execution():
    evidence = [
        {
            "evidence_id": "revenue-2022",
            "source_id": "report",
            "page_label": "4",
            "cell_id": "revenue-2022",
            "evidence_level": "cell",
            "text": "2022 revenue 100 million",
        },
        {
            "evidence_id": "revenue-2023",
            "source_id": "report",
            "page_label": "9",
            "cell_id": "revenue-2023",
            "evidence_level": "cell",
            "text": "2023 revenue 120 million",
        },
    ]
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(
            prompt="What was the percentage change in revenue from 2022 to 2023?",
            task_type="numeric",
            verification_mode="strict",
            verification_domain="finance",
        ),
        {
            "evidence": evidence,
            "finance_numeric_trace": {
                "calculation_plan": {
                    "answer_unit": "percent",
                    "answer_scale": "",
                },
                "calculation_verification": {
                    "valid": True,
                    "citation_ids": [
                        "cell:report:revenue-2022",
                        "cell:report:revenue-2023",
                    ],
                },
                "calculation_execution": {
                    "status": "ok",
                    "value": "20",
                    "citation_ids": [
                        "cell:report:revenue-2022",
                        "cell:report:revenue-2023",
                    ],
                },
            },
        },
    )
    request = DocQARequest(
        prompt="What was the percentage change in revenue from 2022 to 2023?",
        task_type="numeric",
        verification_mode="strict",
        verification_domain="finance",
    )

    decision = verify_decision(
        request,
        _retrieve_decision(),
        bundle,
        "Final answer: 20%.",
    )

    assert decision.status == "supported"
    assert set(decision.verified_citations) == {
        "cell:report:revenue-2022",
        "cell:report:revenue-2023",
    }


def test_calculation_execution_rejects_rendered_value_mismatch():
    item = {
        "evidence_id": "value",
        "source_id": "report",
        "page_label": "1",
        "cell_id": "value",
        "evidence_level": "cell",
        "text": "Revenue 100",
    }
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(prompt="Calculate the result.", task_type="numeric"),
        {
            "evidence": [item],
            "finance_numeric_trace": {
                "calculation_plan": {"answer_unit": "percent", "answer_scale": ""},
                "calculation_verification": {"valid": True},
                "calculation_execution": {
                    "status": "ok",
                    "value": "20",
                    "citation_ids": ["cell:report:value"],
                },
            },
        },
    )
    request = DocQARequest(
        prompt="Calculate the result.",
        task_type="numeric",
        verification_mode="strict",
        verification_domain="finance",
    )

    decision = verify_decision(request, _retrieve_decision(), bundle, "30%.")

    assert decision.status == "unsupported"


def test_numeric_cross_page_operands_require_distinct_pages():
    plan = build_query_plan(
        "Calculate the difference between the table on page 4 "
        "and the chart on page 9.",
        answer_type="numeric",
    )

    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "operand:left",
        "operand:right",
    ]
    assert [slot.modality for slot in plan.evidence_slots] == ["table", "figure"]
    assert plan.constraints["requires_distinct_source_pages"] is True
    partial = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "table-4",
                "source_id": "paper",
                "page_label": "4",
                "modality": "table",
                "text": "table on page 4 value 10",
            }
        ],
    )
    assert [slot.status for slot in partial.evidence_slots] == [
        "filled",
        "missing",
    ]


def test_boolean_cross_page_requires_complete_proposition_evidence():
    plan = build_query_plan(
        "Across pages 4 and 9, did both methods improve accuracy?",
        answer_type="boolean",
    )

    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    ]
    assert plan.constraints["requires_distinct_source_pages"] is True


def test_required_element_rank_21_survives_candidate_supply():
    request = DocQARequest(
        prompt="What does Figure 3 show?",
        task_type="free_text",
        route_policy="hybrid",
    )
    elements = [
        {
            "evidence_id": f"text-{index}",
            "source_id": "paper",
            "page_label": "1",
            "element_id": f"text-{index}",
            "modality": "text",
            "text": f"unrelated element {index}",
        }
        for index in range(20)
    ]
    elements.append(
        {
            "evidence_id": "figure-3",
            "source_id": "paper",
            "page_label": "3",
            "element_id": "figure-3",
            "modality": "figure",
            "caption": "Figure 3 shows the accuracy trend.",
        }
    )

    supplied = _initial_evidence_items(
        "hybrid",
        request,
        {"element_index": elements},
    )

    assert any(item.get("element_id") == "figure-3" for item in supplied)
    assert len(supplied) == 21


def test_rrf_does_not_add_synthetic_text_list_to_dense_bm25():
    item = {
        "evidence_id": "doc-1",
        "source_id": "paper",
        "text": "evidence",
        "retrieval_lineage": [
            {"retriever_name": "dense", "raw_rank": 1, "round_id": 1, "query_id": "q"},
            {"retriever_name": "bm25", "raw_rank": 2, "round_id": 1, "query_id": "q"},
        ],
    }
    request = DocQARequest(prompt="question")
    annotated = _initial_evidence_items(
        "doc",
        request,
        {"evidence": [item]},
    )

    names = {entry["retriever_name"] for entry in annotated[0]["retrieval_lineage"]}
    assert names == {"dense", "bm25"}


def test_rrf_keeps_slot_queries_as_independent_rank_lists():
    items = [
        {
            "evidence_id": f"doc-{index}",
            "source_id": "paper",
            "text": "evidence",
            "retrieval_lineage": [
                {
                    "retriever_name": "dense",
                    "raw_rank": 1,
                    "round_id": 2,
                    "query_id": query_id,
                    "slot_id": query_id,
                }
            ],
        }
        for index, query_id in enumerate(("left", "right"), start=1)
    ]
    weighted_rows: list[tuple[float, int, dict[str, Any], dict[str, Any]]] = [
        (1.0, index, item, {}) for index, item in enumerate(items)
    ]

    rank_lists = _retriever_rank_lists(weighted_rows)

    assert set(rank_lists) == {
        "dense|round:2|query:left",
        "dense|round:2|query:right",
    }


@pytest.mark.parametrize(
    ("slot_modality", "item_modality"),
    [
        ("figure", "page_image"),
        ("table", "page_image"),
        ("formula", "element"),
        ("slide", "page_image"),
    ],
)
def test_slot_modality_compatibility(slot_modality: str, item_modality: str):
    slot = EvidenceSlot(
        slot_id="support",
        role="support",
        metric="accuracy",
        modality=slot_modality,
    )

    assert (
        score_evidence_for_slot(
            slot,
            {
                "evidence_id": "item",
                "source_id": "paper",
                "modality": item_modality,
                "text": "accuracy result",
            },
        )
        > 0
    )


def test_simple_visual_question_requires_visual_evidence():
    plan = build_query_plan("What does Figure 3 show?", answer_type="free_text")

    assert [slot.slot_id for slot in plan.evidence_slots] == ["support:visual_primary"]
    assert plan.evidence_slots[0].modality == "figure"
    assert plan.evidence_slots[0].required_for_retrieval is True


def test_representations_enter_reasoning_text_and_aggregate_subset_is_valid():
    items, _trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "table-page",
                "source_id": "paper",
                "page_label": "2",
                "modality": "table",
                "text": "Values 10 and 12",
            },
            {
                "evidence_id": "table-page",
                "source_id": "paper",
                "page_label": "2",
                "modality": "table",
                "vlm_text": "The highlighted value is 12",
            },
        ]
    )

    assert len(items) == 1
    assert "highlighted value is 12" in evidence_text(items)


def test_boolean_verifier_handles_negated_question_and_explanatory_answer():
    request = DocQARequest(
        prompt="Did the model not use retrieval?",
        task_type="boolean",
        verification_mode="strict",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "method",
                    "source_id": "paper",
                    "text": "The model did not use retrieval.",
                }
            ]
        },
    )

    decision = verify_decision(
        request,
        _retrieve_decision(),
        bundle,
        "Yes. The paper states this explicitly.",
    )

    assert decision.status == "supported"


def test_single_graph_backref_projects_source_and_page():
    item = {
        "evidence_id": "graph-node",
        "element_id": "node",
        "source_backrefs": ["paper#page:7"],
    }

    projected = _graph_locator_items(item, expand=False)

    assert projected[0]["source_id"] == "paper"
    assert projected[0]["page_label"] == "7"


def test_identity_of_recomputes_fields_instead_of_trusting_embedded_identity():
    item = {
        "identity": {
            "source_id": "old-source",
            "kind": "cell",
            "local_id": "old-cell",
        },
        "source_id": "new-source",
        "cell_id": "new-cell",
    }

    assert identity_of(item).key == "cell:new-source:new-cell"


def test_canonicalization_rejects_stale_embedded_identity():
    with pytest.raises(EvidenceIdentityConflictError):
        canonicalize_and_dedupe_evidence(
            [
                {
                    "identity": {
                        "source_id": "old-source",
                        "kind": "cell",
                        "local_id": "old-cell",
                    },
                    "source_id": "new-source",
                    "cell_id": "new-cell",
                }
            ]
        )
