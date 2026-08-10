from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.finance_narrative_answer import finance_narrative_answer
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer


def _page(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    source_id: str = "ULTABEAUTY_2023Q4_EARNINGS",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "page_label": page_label,
        "evidence_level": "page",
        "modality": "text",
        "text": text,
    }


def test_01290_primary_customer_authority_beats_non_us_customer_distractor() -> None:
    question = "Who are the primary customers of Boeing as of FY2022?"

    def candidate(
        evidence_id: str, page: str, text: str, score: float
    ) -> dict[str, Any]:
        return {
            "evidence_id": evidence_id,
            "source_id": "BOEING_2022_10K",
            "page_label": page,
            "evidence_level": "page",
            "text": text,
            "metadata": {"reranking_score": score},
        }

    candidates = [
        candidate(
            "non-us-distractor",
            "12",
            "In 2022, non-U.S. customers including foreign military sales accounted for 41% of revenue.",
            0.99,
        ),
        candidate(
            "airline-authority",
            "8",
            "We derive a significant portion of our revenues from a limited number of commercial airlines.",
            0.10,
        ),
        candidate(
            "government-authority",
            "10",
            "We derive a substantial portion of our revenue from the U.S. government.",
            0.10,
        ),
        candidate(
            "backlog",
            "41",
            "Boeing backlog from customers and revenue contracts.",
            0.80,
        ),
        candidate(
            "business", "3", "Boeing is a major aerospace firm serving customers.", 0.70
        ),
    ]
    selected, _trace, bound = select_evidence_for_plan(
        question,
        candidates,
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
    )

    selected_ids = {str(item.get("evidence_id") or "") for item in selected}
    assert {"airline-authority", "government-authority"} <= selected_ids
    assert identity_of(candidates[0]).key not in {
        evidence_id
        for slot in bound.evidence_slots
        for evidence_id in slot.evidence_ids
    }


@pytest.mark.parametrize(
    ("question", "evidence", "expected_tokens"),
    (
        (
            "As of FY 2021, how much did Verizon expect to pay for its retirees in 2024?",
            (
                "Estimated Future Benefit Payments\nThe benefit payments to retirees are expected to be paid as follows:\n"
                "(dollars in millions)\nYear Pension Benefits Health Care and Life\n2024 $ 1,097 $ 862"
            ),
            ("1,097", "862", "Pension"),
        ),
        (
            "What are three main companies acquired by Pfizer mentioned in this 10K report?",
            (
                "A. Acquisitions\nTrillium\nOn November 17, 2021, we acquired all of the issued and outstanding common stock "
                "of Trillium.\nArray\nOn July 30, 2019, we acquired Array.\nTherachon\nOn July 1, 2019, we acquired all the remaining "
                "shares of Therachon."
            ),
            ("Trillium", "Array", "Therachon"),
        ),
        (
            "What industry does AMCOR primarily operate in?",
            "Today, we are a global leader in developing and producing responsible packaging for food and beverage products.",
            ("packaging",),
        ),
        (
            "Did AMD report customer concentration in FY22?",
            "One customer accounted for 16% of our consolidated net revenue for the year ended December 31, 2022.",
            ("Yes", "16%", "consolidated net revenue"),
        ),
        (
            "Who are the primary customers of Boeing as of FY2022?",
            (
                "We derive a significant portion of our revenues from a limited number of commercial airlines.\n"
                "We derive a substantial portion of our revenue from the U.S. government.\n"
                "In 2022, 40% of our revenues were earned pursuant to U.S. government contracts."
            ),
            ("commercial airlines", "U.S. government", "40%"),
        ),
        (
            "Which debt securities are registered to trade on a national securities exchange under the registrant's name?",
            (
                "Securities registered pursuant to Section 12(b) of the Act:\nTitle of each class Trading symbol Name of each exchange "
                "on which registered\nCommon stock ULTA The NASDAQ Global Select Market\n"
                "Securities registered pursuant to Section 12(g) of the Act: None"
            ),
            ("none",),
        ),
    ),
)
def test_b3_finance_narrative_answers_are_locally_grounded(
    question: str,
    evidence: str,
    expected_tokens: tuple[str, ...],
) -> None:
    item = _page("authority-page", "1", evidence)
    answer = finance_narrative_answer(question, [item])

    assert answer is not None
    assert all(token.lower() in answer.lower() for token in expected_tokens)
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        [item],
    )
    decision = verify_decision(
        DocQARequest(
            prompt=question,
            verification_mode="strict",
            verification_domain="finance",
            query_plan=plan,
        ),
        SimpleNamespace(status="good", retry=False),
        EvidenceBundle(route="text_rag", items=[item], metadata={}),
        answer,
    )
    assert decision.status == "supported"
    assert decision.verified_citations == [identity_of(item).key]


def test_00678_gross_margin_profile_is_audited_calculation_plus_narrative() -> None:
    question = (
        "Does Boeing have an improving gross margin profile as of FY2022? If gross "
        "margin is not a useful metric for a company like this, then state that and explain why."
    )
    page55 = _page(
        "BOEING_2022_10K#page:55",
        "55",
        (
            "The Boeing Company and Subsidiaries\nConsolidated Statements of Operations\n"
            "(Dollars in millions)\nYears ended December 31, 2022 2021 2020\n"
            "Total revenues 66,608 62,286 58,158\n"
            "Total costs and expenses (63,106) (59,269) (63,843)\n"
            "Gross profit 3,502 3,017 (5,685)"
        ),
        source_id="BOEING_2022_10K",
    )
    bundle = SimpleNamespace(items=[page55], metadata={})

    answer = route_finance_numeric_answer(
        SimpleNamespace(prompt=question, verification_domain="finance"),
        SimpleNamespace(route="text_rag"),
        bundle,
    )

    assert answer is not None
    assert all(value in answer for value in ("Yes", "3,502", "3,017", "5.3%", "4.8%"))
    assert (
        bundle.metadata["generation_backend"] == "finance_gross_margin_profile_answerer"
    )
    trace = bundle.metadata["finance_gross_margin_profile_trace"]
    assert trace["audit_status"] == "passed"
    assert trace["citation_ids"] == ["BOEING_2022_10K#page:55"]
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        [page55],
    )
    decision = verify_decision(
        DocQARequest(
            prompt=question,
            verification_mode="strict",
            verification_domain="finance",
            query_plan=plan,
        ),
        SimpleNamespace(status="good", retry=False),
        EvidenceBundle(route="text_rag", items=[page55], metadata={}),
        answer,
    )
    assert decision.status == "supported"
    assert decision.verified_citations == [identity_of(page55).key]


def test_00746_registered_debt_verifier_rejects_positive_rewrite() -> None:
    question = (
        "Which debt securities are registered to trade on a national securities "
        "exchange under the registrant's name?"
    )
    cover = _page(
        "ULTABEAUTY_2023_10K#page:0",
        "0",
        (
            "Securities registered pursuant to Section 12(b) of the Act: "
            "Title of each class Trading symbol Name of each exchange on which "
            "registered Common stock ULTA The NASDAQ Global Select Market "
            "Securities registered pursuant to Section 12(g) of the Act: None"
        ),
    )
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        [cover],
    )
    request = DocQARequest(
        prompt=question,
        verification_mode="strict",
        verification_domain="finance",
        query_plan=plan,
    )
    bundle = EvidenceBundle(route="text_rag", items=[cover], metadata={})

    supported = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        "There are none.",
    )
    contradicted = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        "Senior notes are registered on NASDAQ.",
    )

    assert supported.status == "supported"
    assert supported.verified_citations == [identity_of(cover).key]
    assert contradicted.status == "unsupported"
    assert contradicted.verified_citations == []
