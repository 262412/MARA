from __future__ import annotations

from typing import Any

from ktem.docqa.finance_narrative_answer import finance_narrative_answer
from ktem.docqa.finance_narrative_evidence import finance_narrative_support_quality
from ktem.docqa.finance_verification import finance_numeric_claim_supported
from ktem.reasoning.mara_retrieval_query import retrieval_query


def _page(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    source_id: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "page_label": page_label,
        "evidence_level": "page",
        "modality": "text",
        "text": text,
    }


def test_02024_retiree_claim_with_line_break_is_supported() -> None:
    question = (
        "As of FY 2021, how much did Verizon expect to pay for its retirees in 2024?"
    )
    item = _page(
        "verizon-retiree-authority",
        "94",
        (
            "Estimated Future Benefit Payments The benefit payments to retirees are expected "
            "to be paid as follows: (dollars in millions) Year Pension Benefits Health Care "
            "and Life 2024 $ 1,097 $ 862"
        ),
        source_id="VERIZON_2021_10K",
    )
    claim = (
        "Pension benefits were $1,097 million\n"
        "health care and life insurance benefits were $862 million."
    )

    assert finance_numeric_claim_supported(claim, [item], prompt=question) is True


def test_01148_industry_claim_with_line_break_is_supported() -> None:
    question = "What industry does AMCOR primarily operate in?"
    item = _page(
        "amcor-industry-authority",
        "30",
        (
            "Today, we are a global leader in developing and producing responsible "
            "packaging for food, beverage, pharmaceutical, medical, home and personal-care "
            "and other products."
        ),
        source_id="AMCOR_2022_10K",
    )
    claim = (
        "A global leader in developing and producing responsible packaging for food, "
        "beverage, pharmaceutical, medical, home and personal-care\nother products."
    )

    assert finance_numeric_claim_supported(claim, [item], prompt=question) is True


def test_01198_revenue_driver_claim_is_verification_authoritative() -> None:
    question = "What drove revenue change as of the FY22 for AMD?"
    item = _page(
        "amd-revenue-driver-authority",
        "43",
        (
            "Net revenue for 2022 was $23.6 billion, an increase of 44% compared to "
            "2021 net revenue of $16.4 billion. The increase in net revenue was driven "
            "by a 64% increase in Data Center segment revenue primarily due to higher sales "
            "of our EPYC server processors, a 21% increase in Gaming segment revenue "
            "primarily due to higher semi-custom product sales, and a significant increase "
            "in Embedded segment revenue from the prior year period driven by the inclusion "
            "of Xilinx embedded product sales."
        ),
        source_id="AMD_2022_10K",
    )
    answer = finance_narrative_answer(question, [item])

    assert answer is not None
    assert finance_numeric_claim_supported(answer, [item], prompt=question) is True


def test_01290_primary_customer_claim_requires_fy2022_share_fact() -> None:
    question = "Who are the primary customers of Boeing as of FY2022?"
    item = _page(
        "boeing-primary-customer-authority",
        "8",
        (
            "We derive a significant portion of our revenues from a limited number of "
            "commercial airlines. We derive a substantial portion of our revenue from the "
            "U.S. government. In 2022, 40% of our revenues were earned pursuant to U.S. "
            "government contracts."
        ),
        source_id="BOEING_2022_10K",
    )
    incomplete_claim = (
        "Boeing's primary customers are a limited number of commercial airlines and the "
        "U.S. government."
    )

    assert (
        finance_numeric_claim_supported(incomplete_claim, [item], prompt=question)
        is False
    )
    complete_answer = finance_narrative_answer(question, [item])
    assert complete_answer is not None
    assert (
        finance_numeric_claim_supported(complete_answer, [item], prompt=question)
        is True
    )
    prefix_claim = complete_answer.rsplit(" In ", 1)[0]
    assert prefix_claim in complete_answer
    assert (
        finance_numeric_claim_supported(prefix_claim, [item], prompt=question) is False
    )


def test_primary_customer_facts_must_share_one_canonical_evidence_item() -> None:
    question = "Who are the primary customers of Boeing as of FY2022?"
    claim = (
        "Commercial airlines and the U.S. government were primary customers. "
        "In 2022, 40% of revenues came from U.S. government contracts."
    )
    split_items = [
        _page(
            "customer-types",
            "8",
            (
                "We derive revenue from a limited number of commercial airlines and "
                "a substantial portion from the U.S. government."
            ),
            source_id="BOEING_2022_10K",
        ),
        _page(
            "government-share",
            "9",
            (
                "In 2022, 40% of our revenues were earned pursuant to U.S. "
                "government contracts."
            ),
            source_id="BOEING_2022_10K",
        ),
    ]

    assert finance_numeric_claim_supported(claim, split_items, prompt=question) is False


def test_00757_customer_concentration_focus_requests_annual_net_revenue_fact() -> None:
    question = "Did AMD report customer concentration in FY22?"
    query = retrieval_query(question, domain="finance").lower()

    assert "one customer accounted for" in query
    assert "consolidated net revenue" in query
    assert "year ended" in query

    target = {
        "evidence_id": "amd-customer-revenue",
        "source_id": "AMD_2022_10K",
        "page_label": "12",
        "evidence_level": "page",
        "text": (
            "One customer accounted for 17% of our consolidated net revenue "
            "for the year ended December 31, 2022."
        ),
    }
    distractor = {
        "evidence_id": "amd-customer-receivables",
        "source_id": "AMD_2022_10K",
        "page_label": "80",
        "evidence_level": "page",
        "text": (
            "One customer accounted for 18% of the total consolidated accounts "
            "receivable balance as of December 31, 2022."
        ),
    }

    assert finance_narrative_support_quality(
        question, target
    ) > finance_narrative_support_quality(question, distractor)
