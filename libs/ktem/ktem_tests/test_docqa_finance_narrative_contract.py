from types import SimpleNamespace

from ktem.docqa.finance_narrative_answer import finance_narrative_answer
from ktem.docqa.finance_typed_adequacy import (
    ensure_finance_numeric_trace,
    typed_calculation_adequacy,
)
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_claim
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer


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


def test_full_year_sga_driver_uses_local_annual_sentence_and_fiscal_alias() -> None:
    question = (
        "What drove the reduction in SG&A expense as a percent of net sales in FY2023?"
    )
    period_alias_page = {
        "evidence_id": "ulta-results-cover",
        "source_id": "ulta",
        "page_label": "1",
        "evidence_level": "page",
        "text": (
            "Ulta announced results for the fifty-two-week period (fiscal year) "
            "ended January 28, 2023."
        ),
    }
    annual_page = {
        "evidence_id": "ulta-results-page",
        "source_id": "ulta",
        "page_label": "2",
        "evidence_level": "page",
        "text": (
            "For the Fourth Quarter of Fiscal 2022, as a "
            "percentage of net sales, SG&A expenses decreased primarily due to "
            "leverage of marketing expenses and incentive compensation due to "
            "higher sales. For the Full Year of Fiscal 2022, SG&A expenses "
            "increased 16.2%. As a percentage of net sales, SG&A expenses "
            "decreased to 23.5% from 23.9%, primarily due to lower marketing "
            "expenses and leverage of incentive compensation due to higher sales, "
            "partially offset by deleverage of corporate overhead."
        ),
    }
    later_distractor = {
        "evidence_id": "ulta-results-appendix",
        "source_id": "ulta",
        "page_label": "7",
        "evidence_level": "page",
        "text": "52 Weeks Ended January 28, 2023. Cosmetics represented 42%.",
    }

    evidence = [period_alias_page, annual_page, later_distractor]
    answer = finance_narrative_answer(question, evidence)

    assert answer is not None
    assert "lower marketing expenses" in answer.lower()
    assert "leverage of incentive compensation due to higher sales" in answer.lower()
    assert "leverage of marketing expenses" not in answer.lower()

    bundle = SimpleNamespace(items=evidence, metadata={})
    routed = route_finance_numeric_answer(
        SimpleNamespace(prompt=question, verification_domain="finance"),
        SimpleNamespace(route="text_rag"),
        bundle,
    )
    verified = verify_claim(
        str(routed),
        evidence,
        claim_id="claim:1",
        prompt=question,
        domain="finance",
    )

    assert routed == answer
    assert bundle.metadata["generation_backend"] == "finance_narrative_answerer"
    assert verified.status == "supported"
