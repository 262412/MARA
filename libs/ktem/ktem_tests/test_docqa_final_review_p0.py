from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_plan_schema import EvidenceLocator, EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan, score_evidence_for_slot
from ktem.docqa.required_slot_selection import required_slot_shortlist
from ktem.docqa.verification import verify_decision, with_verification_evidence


def _retrieve_decision():
    return SimpleNamespace(status="good", retry=False)


def test_page_slot_matches_page_label_without_page_text():
    slot = EvidenceSlot(
        slot_id="support:page_9",
        role="support",
        modality="page_image",
        locator=EvidenceLocator(page_label="9"),
    )

    assert (
        score_evidence_for_slot(
            slot,
            {
                "evidence_id": "page-image",
                "source_id": "paper",
                "page_label": "9",
                "modality": "page_image",
                "ocr_text": "No page number appears in this text.",
            },
        )
        > 0
    )


def test_visual_slot_rejects_unrelated_compatible_page():
    plan = build_query_plan("What does Figure 3 show?", answer_type="free_text")
    slot = plan.evidence_slots[0]

    assert (
        score_evidence_for_slot(
            slot,
            {
                "evidence_id": "figure-4",
                "source_id": "paper",
                "page_label": "4",
                "element_id": "figure-4",
                "figure_label": "4",
                "modality": "figure",
                "text": "An unrelated visual.",
            },
        )
        == 0
    )


def test_structured_cell_slot_uses_row_period_value_fields():
    slot = EvidenceSlot(
        slot_id="operand:revenue_2023",
        role="operand",
        metric="revenue",
        period="2023",
        required_for_execution=True,
        locator=EvidenceLocator(table_label="income-statement"),
    )
    item = {
        "evidence_id": "table-parent",
        "source_id": "report",
        "cell_id": "revenue-2023",
        "table_id": "income-statement",
        "row_label": "Revenue",
        "period": "2023",
        "value": "120",
        "modality": "table",
        "text": "",
    }

    assert score_evidence_for_slot(slot, item, requires_structure=True) > 0


def test_multi_period_between_preserves_metric_and_periods():
    plan = build_query_plan(
        "What was the percentage change in revenue between 2021 and 2022?",
        answer_type="numeric",
    )

    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("revenue", "2021"),
        ("revenue", "2022"),
    ]


def test_required_slot_quota_preserves_distinct_pages():
    plan = QueryPlan(
        answer_type="free_text",
        question_type="cross_page",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:left",
                role="support",
                metric="result",
                locator=EvidenceLocator(page_label="4"),
            ),
            EvidenceSlot(
                slot_id="support:right",
                role="support",
                metric="limitation",
                locator=EvidenceLocator(page_label="9"),
            ),
        ),
        constraints={
            "requires_distinct_evidence": True,
            "requires_distinct_source_pages": True,
            "distinct_source_page_slot_ids": ("support:left", "support:right"),
        },
    )
    items = [
        {
            "evidence_id": "page-4-a",
            "source_id": "paper",
            "page_label": "4",
            "text": "result limitation",
        },
        {
            "evidence_id": "page-4-b",
            "source_id": "paper",
            "page_label": "4",
            "text": "result limitation",
        },
        {
            "evidence_id": "page-9",
            "source_id": "paper",
            "page_label": "9",
            "text": "limitation",
        },
    ]

    selected, _restored = required_slot_shortlist(items, plan, candidate_limit=2)

    assert {(item["source_id"], item["page_label"]) for item in selected} == {
        ("paper", "4"),
        ("paper", "9"),
    }


def test_required_page_image_beyond_rank_20_survives():
    request = DocQARequest(
        prompt="What is reported on page 25?",
        task_type="free_text",
        route_policy="doc_page_image",
    )
    pages = [
        {
            "evidence_id": f"page-{index}",
            "source_id": "paper",
            "page_label": str(index),
            "modality": "page_image",
            "ocr_text": "unrelated",
        }
        for index in range(1, 25)
    ]
    pages.append(
        {
            "evidence_id": "page-25",
            "source_id": "paper",
            "page_label": "25",
            "modality": "page_image",
            "ocr_text": "reported result",
        }
    )

    bundle = build_evidence_bundle(
        "doc_page_image",
        request,
        {"page_image_index": pages},
    )

    assert any(
        item.get("page_label") == "25"
        for item in bundle.metadata["reranker_input_evidence"]
    )


def test_post_fusion_and_reranker_input_are_distinct_stages():
    request = DocQARequest(
        prompt="Compare the result on pages 4 and 9.",
        task_type="free_text",
        route_policy="hybrid",
    )
    evidence = [
        {
            "evidence_id": f"candidate-{index}",
            "source_id": "paper",
            "page_label": str(index),
            "text": f"result {index}",
        }
        for index in range(1, 90)
    ]

    bundle = build_evidence_bundle("hybrid", request, {"evidence": evidence})

    assert (
        bundle.metadata["fused_evidence"]
        == bundle.metadata["candidate_ranked_evidence"]
    )
    assert len(bundle.metadata["fused_evidence"]) > len(
        bundle.metadata["reranker_input_evidence"]
    )


def test_learned_reranker_executes_after_fusion_input_is_frozen():
    class _Ranker:
        name = "fixture-reranker"

        def score(self, _query, item):
            return 1.0 if item["evidence_id"] == "text" else 0.0

    request = DocQARequest(
        prompt="Explain the revenue table.",
        task_type="free_text",
        route_policy="hybrid",
    )
    bundle = build_evidence_bundle(
        "hybrid",
        request,
        {
            "hybrid_fusion_ranker": _Ranker(),
            "evidence": [
                {
                    "evidence_id": "text",
                    "source_id": "paper",
                    "page_label": "1",
                    "text": "Revenue table context.",
                }
            ],
            "element_index": [
                {
                    "evidence_id": "element",
                    "source_id": "paper",
                    "page_label": "1",
                    "element_id": "table-1",
                    "modality": "table",
                    "text": "Revenue table.",
                }
            ],
        },
    )

    assert bundle.metadata["fused_evidence"][0]["evidence_id"] == "element"
    assert bundle.metadata["reranker_input_evidence"][0]["evidence_id"] == "element"
    assert bundle.metadata["reranked_evidence"][0]["evidence_id"] == "text"


def test_calculation_verifier_materializes_parent_table_cells():
    parent = {
        "evidence_id": "income-table",
        "source_id": "report",
        "page_label": "5",
        "table_id": "income-table",
        "modality": "table",
        "text": "Income statement\n2022 2023\nRevenue 100 120",
    }
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(prompt="Calculate revenue growth.", task_type="numeric"),
        {
            "evidence": [parent],
            "finance_numeric_trace": {
                "calculation_plan": {"answer_unit": "percent", "answer_scale": ""},
                "calculation_verification": {"valid": True},
                "calculation_execution": {
                    "status": "ok",
                    "value": "20",
                    "citation_ids": [
                        "cell:report:source%3Areport#page%3A5"
                        "#table-instance%3Aincome-table#block%3Aincome-table"
                        "#row%3A1#column%3A1"
                    ],
                },
            },
        },
    )
    request = DocQARequest(
        prompt="Calculate revenue growth.",
        task_type="numeric",
        verification_mode="strict",
        verification_domain="finance",
    )

    decision = verify_decision(request, _retrieve_decision(), bundle, "20 percent")
    verified = with_verification_evidence(bundle, decision)

    assert decision.status == "supported"
    assert verified.metadata["verified_evidence"][0]["evidence_level"] == "cell"
    assert verified.metadata["verified_evidence"][0]["row_label"] == "Revenue"


def test_numeric_execution_does_not_validate_extra_false_claim():
    item = {
        "evidence_id": "revenue",
        "source_id": "report",
        "page_label": "5",
        "cell_id": "revenue",
        "evidence_level": "cell",
        "text": "Revenue increased by 20 percent. Costs decreased.",
    }
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(prompt="Calculate revenue growth.", task_type="numeric"),
        {
            "evidence": [item],
            "finance_numeric_trace": {
                "calculation_plan": {"answer_unit": "percent", "answer_scale": ""},
                "calculation_verification": {"valid": True},
                "calculation_execution": {
                    "status": "ok",
                    "value": "20",
                    "citation_ids": [identity_of(item).key],
                },
            },
        },
    )
    request = DocQARequest(
        prompt="Calculate revenue growth.",
        task_type="numeric",
        verification_mode="strict",
        verification_domain="finance",
    )

    decision = verify_decision(
        request,
        _retrieve_decision(),
        bundle,
        "Revenue growth was 20 percent. Costs increased.",
    )

    assert decision.status != "supported"
    assert len(decision.claim_results) == 2
