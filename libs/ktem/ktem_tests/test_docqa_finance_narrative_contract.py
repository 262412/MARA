from types import SimpleNamespace

from ktem.docqa.finance_typed_adequacy import (
    ensure_finance_numeric_trace,
    typed_calculation_adequacy,
)
from ktem.docqa.query_planning import build_query_plan


def test_explanatory_percent_language_does_not_activate_calculation_contract():
    question = "What drove the reduction in selling expenses as a percent of net sales?"
    plan = build_query_plan(
        question,
        answer_type="extractive",
        verification_domain="finance",
        planner_payload={
            "answer_type": "extractive",
            "question_type": "long_form",
            "evidence_slots": [
                {
                    "slot_id": "support:primary",
                    "role": "support",
                    "query": question,
                }
            ],
        },
    )

    assert plan.answer_type == "extractive"
    assert plan.question_type == "long_form"
    assert plan.constraints.get("finance_formula_status") in {
        None,
        "not_applicable",
    }
    assert not any(slot.required_for_execution for slot in plan.evidence_slots)

    bundle = SimpleNamespace(
        items=[
            {
                "evidence_id": "driver",
                "source_id": "report",
                "text": "The reduction was driven by lower advertising costs.",
            }
        ],
        metadata={"query_plan": plan.as_dict()},
    )
    ensure_finance_numeric_trace(
        SimpleNamespace(
            prompt=question,
            verification_domain="finance",
            query_plan=plan,
        ),
        bundle,
    )

    assert "finance_numeric_trace" not in bundle.metadata
    assert typed_calculation_adequacy(
        bundle.metadata,
        domain="finance",
    ) == ("not_applicable", "non_numeric_query_plan")
