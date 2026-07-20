from ktem.docqa.query_planning import (
    bind_evidence_slots,
    build_query_plan,
    missing_slot_queries,
    retrieval_budget,
)


def test_numeric_comparison_plan_has_distinct_required_period_operands():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )

    assert plan.answer_type == "numeric"
    assert plan.question_type == "multi_period_numeric"
    assert [slot.period for slot in plan.evidence_slots] == ["2021", "2022"]
    assert all(slot.required for slot in plan.evidence_slots)
    assert all(slot.role == "operand" for slot in plan.evidence_slots)
    assert plan.max_retrieval_rounds == 2
    assert retrieval_budget(plan) == {"max_items": 16, "max_pages": 6}


def test_slot_binding_and_missing_queries_only_target_unfilled_operand():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    bound = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "revenue-2021",
                "text": "Revenue was $10 million in 2021.",
                "page_label": "4",
                "modality": "table",
            }
        ],
    )

    assert bound.evidence_slots[0].status == "filled"
    assert bound.evidence_slots[0].evidence_ids == ("revenue-2021",)
    assert bound.evidence_slots[1].status == "missing"
    assert missing_slot_queries(bound) == ["revenue 2022"]


def test_long_form_plan_uses_long_answer_budget_without_numeric_slots():
    plan = build_query_plan(
        "Explain why the paper introduces a retrieval reranker.",
        answer_type="free_text",
    )

    assert plan.question_type == "long_form"
    assert retrieval_budget(plan) == {"max_items": 12, "max_pages": 5}
