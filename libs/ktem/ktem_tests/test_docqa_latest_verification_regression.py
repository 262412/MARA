from types import SimpleNamespace

from ktem.docqa.calculation_claim_verification import calculation_claim_result
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan
from ktem.docqa.verification import verify_claim, verify_decision


def test_domain_false_without_explicit_counterevidence_remains_unknown() -> None:
    evidence = [
        {
            "evidence_id": "assets",
            "source_id": "report",
            "row_label": "Current assets",
            "value": "90",
            "text": "Current assets were 90.",
        },
        {
            "evidence_id": "inventory",
            "source_id": "report",
            "row_label": "Inventories",
            "value": "10",
            "text": "Inventories were 10.",
        },
        {
            "evidence_id": "liabilities",
            "source_id": "report",
            "row_label": "Current liabilities",
            "value": "100",
            "text": "Current liabilities were 100.",
        },
    ]

    result = verify_claim(
        "The quick-ratio view shows a healthy liquidity profile.",
        evidence,
        claim_id="claim:1",
        prompt="Does the company have a healthy liquidity profile based on quick ratio?",
        domain="finance",
    )

    assert result.status == "unknown"
    assert result.contradicting_evidence_ids == ()


def test_currency_amount_that_looks_like_a_year_remains_a_numeric_claim() -> None:
    question = "What was adjusted non-GAAP EBITDA for FY2023 in USD millions?"
    cell = _adjusted_ebitda_cell("2018")
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [cell],
    )
    answer = finance_numeric_answer(question, [cell], query_plan=plan.as_dict())
    assert answer is not None
    bundle = EvidenceBundle(
        route="doc_text",
        items=[cell],
        metadata={"finance_numeric_trace": answer.as_trace()},
    )

    result = calculation_claim_result(
        bundle,
        "$2,018 million",
        ["$2,018 million"],
        domain="finance",
        prompt=question,
    )

    assert result is not None
    assert result.status == "supported"


def test_verifier_uses_latest_bundle_plan_after_second_round_binding() -> None:
    question = "What was adjusted non-GAAP EBITDA for FY2023 in USD millions?"
    cell = _adjusted_ebitda_cell("1500")
    stale_plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    bound_plan = bind_evidence_slots(stale_plan, [cell])
    answer = finance_numeric_answer(
        question,
        [cell],
        query_plan=bound_plan.as_dict(),
    )
    assert answer is not None
    authoritative_plan = {
        **bound_plan.as_dict(),
        "state_authority": "verified_calculation_plan",
    }
    bundle = EvidenceBundle(
        route="doc_text",
        items=[cell],
        metadata={
            "finance_numeric_trace": answer.as_trace(),
            "query_plan": authoritative_plan,
        },
    )
    request = SimpleNamespace(
        prompt=question,
        controller_question=question,
        verification_domain="finance",
        verification_mode="light",
        origin="benchmark",
        query_plan=stale_plan,
    )

    result = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        answer.answer,
    )

    assert result.status == "supported"
    assert result.verified_citations


def _adjusted_ebitda_cell(value: str) -> dict[str, str]:
    return {
        "evidence_id": "adjusted-ebitda-2023",
        "source_id": "amcor",
        "page_label": "1",
        "evidence_level": "cell",
        "cell_id": "adjusted-ebitda-2023",
        "row_label": "Adjusted EBITDA",
        "column_label": "2023",
        "period": "2023",
        "period_kind": "fiscal_year",
        "value": value,
        "scale": "million",
        "currency": "USD",
        "statement_kind": "non_gaap_performance",
        "text": f"Adjusted EBITDA 2023 {value} million USD.",
    }
