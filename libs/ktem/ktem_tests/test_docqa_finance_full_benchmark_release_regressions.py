from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceBundle, _materialize_execution_cells
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan, missing_slot_requests
from ktem.docqa.verification import verify_decision, with_verification_evidence
from ktem.docqa.verification_slot_support import claim_aware_slot_support
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer
from ktem.reasoning.mara_retrieval_query import retrieval_query

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.task_answer_contracts import synchronize_terminal_answer_state

SGA_QUESTION = (
    "What drove the reduction in SG&A expense as a percent of net sales in FY2023?"
)
SGA_ANSWER = (
    "Lower marketing expenses and leverage of incentive compensation due to higher sales, "
    "partially offset by deleverage of corporate overhead due to strategic investments "
    "and deleverage of store payroll and benefits due to wage investments"
)


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


def _amd_segment_cell(
    row_label: str,
    period: str,
    value: str,
    *,
    page_label: str = "48",
    statement_kind: str = "segment_table",
    financial_scope: str = "segment",
) -> dict[str, Any]:
    cell_id = f"amd-segment-{row_label.lower().replace(' ', '-')}-{period}"
    return {
        "evidence_id": cell_id,
        "cell_id": cell_id,
        "source_id": "AMD_2022_10K",
        "page_label": page_label,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "period_kind": "fiscal_year",
        "value": value,
        "unit": "USD",
        "scale": "million",
        "currency": "USD",
        "statement_kind": statement_kind,
        "financial_scope": financial_scope,
        "text": f"AMD reporting segment {row_label} {period} {value} million.",
    }


def test_00563_segment_comparison_uses_page48_matrix_and_ignores_page67_distractor() -> None:
    question = (
        "From FY21 to FY22, excluding Embedded, in which AMD reporting segment did sales "
        "proportionally increase the most?"
    )
    page48 = {
        "evidence_id": "AMD_2022_10K#page:48",
        "source_id": "AMD_2022_10K",
        "page_label": "48",
        "modality": "table",
        "text": (
            "AMD net revenue by reporting segment (in millions)\n"
            "Year Ended December 31, 2022 2021\n"
            "Net revenue:\nData Center\n$\n6,043\n$\n3,694\n"
            "Client\n6,201\n6,887\nGaming\n6,805\n5,607\n"
            "Embedded\n4,552\n246\nTotal net revenue\n$\n23,601\n$\n16,434\n"
            "Operating income (loss):\nData Center\n$\n1,848\n$\n991"
        ),
    }
    page67 = {
        "evidence_id": "AMD_2022_10K#page:67",
        "source_id": "AMD_2022_10K",
        "page_label": "67",
        "modality": "text",
        "text": (
            "Revenue recognition and performance obligations. The following discussion "
            "describes contract consideration and remaining performance obligations."
        ),
    }

    result = finance_segment_comparison_answer(question, [page48, page67])

    assert result is not None
    assert result.answer == "Data Center"
    assert result.status == "ok"
    assert result.citation_ids == ("AMD_2022_10K#page:48",)
    assert set(result.entity_period_values) == {"Data Center", "Client", "Gaming"}


def test_00563_query_plan_rejects_total_revenue_cells_as_segment_operands() -> None:
    question = (
        "From FY21 to FY22, excluding Embedded, in which AMD reporting segment did sales "
        "proportionally increase the most?"
    )
    total_cells = [
        _amd_segment_cell("Total net revenue", "2021", "16434"),
        _amd_segment_cell("Total net revenue", "2022", "23601"),
        _amd_segment_cell(
            "Data Center",
            "2021",
            "3694",
            page_label="67",
            statement_kind="income_statement",
            financial_scope="consolidated",
        ),
    ]
    plan = bind_evidence_slots(
        build_query_plan(question, verification_domain="finance"),
        total_cells,
    )

    assert all(slot.status == "missing" for slot in plan.evidence_slots)
    assert all(not slot.evidence_ids for slot in plan.evidence_slots)


def _ulta_page2() -> dict[str, Any]:
    return _page(
        "ULTABEAUTY_2023Q4_EARNINGS#page:2",
        "2",
        (
            "For the full year, SG&A expenses as a percentage of net sales decreased "
            "primarily due to lower marketing expenses and leverage of incentive "
            "compensation due to higher sales, partially offset by deleverage of corporate "
            "overhead due to strategic investments and deleverage of store payroll and "
            "benefits due to wage investments."
        ),
    )


def _ulta_runtime_state() -> tuple[DocQARequest, EvidenceBundle, Any, str]:
    page2 = _ulta_page2()
    plan = bind_evidence_slots(
        build_query_plan(
            SGA_QUESTION, answer_type="extractive", verification_domain="finance"
        ),
        [page2],
    )
    request = DocQARequest(
        prompt=SGA_QUESTION,
        verification_mode="strict",
        verification_domain="finance",
        query_plan=plan,
    )
    bundle = EvidenceBundle(
        route="text_rag", items=[page2], metadata={"query_plan": plan.as_dict()}
    )
    decision = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        answer=SGA_ANSWER,
    )
    verified = with_verification_evidence(bundle, decision, request=request)
    return request, verified, decision, identity_of(page2).key


def test_00601_runtime_claim_support_reconciles_to_one_page2_canonical_id() -> None:
    request, bundle, decision, canonical_id = _ulta_runtime_state()

    assert decision.status == "supported"
    assert claim_aware_slot_support(
        request,
        decision,
        bundle,
        prompt=SGA_QUESTION,
        domain="finance",
    ) == {"support:primary": (canonical_id,)}
    assert bundle.metadata["verification_slot_states"] == [
        {
            "slot_id": "support:primary",
            "status": "verified_support",
            "evidence_ids": [canonical_id],
        }
    ]
    assert [
        identity_of(item).key
        for item in bundle.metadata["verified_claim_support_evidence"]
    ] == [canonical_id]


def _terminal_prediction() -> tuple[dict[str, Any], str]:
    _request, bundle, decision, canonical_id = _ulta_runtime_state()
    page2 = bundle.items[0]
    citation = {
        "kind": "page",
        "evidence_id": canonical_id,
        "source_id": page2["source_id"],
        "page_label": page2["page_label"],
        "span": SGA_ANSWER,
    }
    metadata = {
        **bundle.metadata,
        "selected_evidence": [page2],
        "generation_context_evidence": [page2],
        "query_plan": bundle.metadata["query_plan"],
        "verify_decision": decision.as_dict(),
        "verified_claim_support_evidence": [page2],
        "verified_evidence": [page2],
    }
    prediction: dict[str, Any] = {
        "question": SGA_QUESTION,
        "answer_type": "extractive",
        "predicted_answer": SGA_ANSWER,
        "route": "text_rag",
        "gold_evidence": [canonical_id],
        "task_answer_contract": {
            "contract_id": "financebench_answerability.v1",
            "status": "applied",
        },
        "evidence_bundle": {
            "items": [page2],
            "metadata": metadata,
        },
        "evidence_metadata": metadata,
        "verify_decision": decision.as_dict(),
        "claim_verification": {
            "status": "supported",
            "claim_results": decision.claim_results,
        },
        "structured_citations": [citation],
        "predicted_citations": [f"{page2['source_id']}#page:{page2['page_label']}"],
    }
    return prediction, canonical_id


def test_00601_finance_terminal_sync_reconciles_query_plan_and_page2_identity() -> None:
    prediction, canonical_id = _terminal_prediction()

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    assert synchronize_terminal_answer_state(prediction)
    terminal = prediction["terminal_answer_state"]
    metadata = prediction["evidence_metadata"]
    assert {
        identity_of(item).key for item in metadata["verified_claim_support_evidence"]
    } == {canonical_id}
    assert {identity_of(item).key for item in terminal["supporting_evidence"]} == {
        canonical_id
    }
    assert {
        str(item.get("evidence_id") or "") for item in terminal["emitted_citations"]
    } == {canonical_id}
    query_plan = metadata.get("terminal_query_plan") or metadata.get("query_plan")
    assert str(query_plan.get("state_authority") or "").endswith(".v1")


@pytest.mark.parametrize("state", ("missing", "incompatible", "invalid_support"))
def test_00601_non_authoritative_support_clears_terminal_citations(state: str) -> None:
    page2 = _ulta_page2()
    page3 = _page(
        "ULTABEAUTY_2023Q4_EARNINGS#page:3",
        "3",
        "Balance sheet and store count information.",
    )
    support = {
        "missing": [],
        "incompatible": [page3],
        "invalid_support": [{"evidence_id": "garbage:page2", "text": SGA_ANSWER}],
    }[state]
    prediction: dict[str, Any] = {
        "question": SGA_QUESTION,
        "answer_type": "extractive",
        "predicted_answer": SGA_ANSWER,
        "route": "text_rag",
        "gold_evidence": [identity_of(page2).key],
        "evidence_bundle": {"items": [page2, page3], "metadata": {}},
        "evidence_metadata": {
            "evidence": [page2, page3],
            "selected_evidence": [page2, page3],
            "verified_claim_support_evidence": support,
        },
        "structured_citations": [
            {
                "kind": "page",
                "source_id": page2["source_id"],
                "page_label": page2["page_label"],
                "span": SGA_ANSWER,
            }
        ],
        "predicted_citations": [f"{page2['source_id']}#page:2"],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []
    assert prediction["evidence_metadata"].get("emitted_citation_evidence") == []


def test_00601_structured_answer_cannot_reintroduce_unverified_citation() -> None:
    page2 = _ulta_page2()
    prediction: dict[str, Any] = {
        "question": SGA_QUESTION,
        "answer_type": "extractive",
        "predicted_answer": (
            '{"answer": "Lower marketing expenses", "citations": '
            '[{"source_id": "ULTABEAUTY_2023Q4_EARNINGS", "page": "2"}]}'
        ),
        "route": "text_rag",
        "gold_evidence": [identity_of(page2).key],
        "evidence_bundle": {"items": [page2], "metadata": {}},
        "evidence_metadata": {
            "selected_evidence": [page2],
            "generation_context_evidence": [page2],
        },
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )
    synchronized = synchronize_terminal_answer_state(prediction)

    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []
    assert synchronized
    assert prediction["answer_for_scoring"] == "unanswerable"
    assert prediction["terminal_answer_state"]["supporting_evidence"] == []


def test_00882_revolving_capacity_operands_require_local_unit_and_scale_provenance() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    page = {
        "evidence_id": "pepsico-page-2",
        "source_id": "pepsico",
        "page_label": "2",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Effective May 26, 2023, PepsiCo terminated the $3,800,000,000 364 day "
            "unsecured revolving credit agreement. On May 26, 2023, PepsiCo entered "
            "into a new $4,200,000,000 364 day unsecured revolving credit agreement "
            "(the 2023 364 Day Credit Agreement). The 2023 364 Day Credit Agreement "
            "enables PepsiCo to borrow up to $4,200,000,000. Effective May 26, 2023, "
            "PepsiCo terminated the $3,800,000,000 five year unsecured revolving credit "
            "agreement. On May 26, 2023, PepsiCo entered into a new $4,200,000,000 five "
            "year unsecured revolving credit agreement (the 2023 Five Year Credit "
            "Agreement). The 2023 Five Year Credit Agreement enables PepsiCo to borrow "
            "up to $4,200,000,000."
        ),
    }
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
    )
    expanded = _materialize_execution_cells(request, [page], {})
    bound = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=bound.as_dict())

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert answer.attempt_status == "executed"
    operands = answer.calculation_plan["operands"]
    assert len(operands) == 2
    assert all(operand.get("unit") for operand in operands)
    assert all(operand.get("scale") for operand in operands)
    assert all(operand.get("scale_evidence_identity") for operand in operands)
    assert len({operand["evidence_identity"] for operand in operands}) == 2


def test_00882_empty_unit_and_scale_provenance_fails_closed() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    evidence = [
        {
            "evidence_id": "active-364",
            "source_id": "pepsico",
            "page_label": "2",
            "evidence_level": "span",
            "span_id": "active-364",
            "row_label": "revolving credit capacity",
            "period": "2023",
            "value": "4200000000",
            "text": "new $4,200,000,000 364 day unsecured revolving credit agreement",
            "metadata": {
                "agreement_lifecycle_status": "active",
                "facility_type": "364_day",
            },
        },
        {
            "evidence_id": "active-five-year",
            "source_id": "pepsico",
            "page_label": "2",
            "evidence_level": "span",
            "span_id": "active-five-year",
            "row_label": "revolving credit capacity",
            "period": "2023",
            "value": "4200000000",
            "text": "new $4,200,000,000 five year unsecured revolving credit agreement",
            "metadata": {
                "agreement_lifecycle_status": "active",
                "facility_type": "five_year",
            },
        },
    ]
    plan = build_query_plan(
        question, answer_type="numeric", verification_domain="finance"
    )
    bound = bind_evidence_slots(plan, evidence)
    answer = finance_numeric_answer(question, evidence, query_plan=bound.as_dict())

    assert answer is not None
    assert answer.attempt_status == "verification_failed"
    assert answer.calculation_execution["status"] == "error"


def test_01198_revenue_driver_is_narrative_not_formula() -> None:
    question = "What drove revenue change as of the FY22 for AMD?"
    page43 = _page(
        "AMD_2022_10K#page:43",
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
    bundle = SimpleNamespace(items=[page43], metadata={})

    routed = route_finance_numeric_answer(
        SimpleNamespace(prompt=question, verification_domain="finance"),
        SimpleNamespace(route="text_rag"),
        bundle,
    )

    assert routed
    assert all(token in routed for token in ("EPYC", "semi-custom", "Xilinx"))
    assert bundle.metadata["generation_backend"] == "finance_narrative_answerer"
    assert "finance_numeric_trace" not in bundle.metadata


@pytest.mark.parametrize(
    ("question", "required_focus"),
    (
        (
            "As of FY 2021, how much did Verizon expect to pay for its retirees in 2024?",
            (
                "Estimated Future Benefit Payments",
                "Pension Benefits",
                "Health Care and Life",
            ),
        ),
        (
            "What are three main companies acquired by Pfizer mentioned in this 10K report?",
            (
                "Note Acquisitions",
                "wholly owned subsidiary",
                "acquired all outstanding shares",
            ),
        ),
        (
            "What industry does AMCOR primarily operate in?",
            ("Item 1 Business", "company overview", "global leader"),
        ),
        (
            "Did AMD report customer concentration in FY22?",
            (
                "one customer accounted for",
                "consolidated net revenue",
                "major customer",
            ),
        ),
        (
            "Who are the primary customers of Boeing as of FY2022?",
            (
                "limited number of commercial airlines",
                "U.S. government contracts",
                "percent of revenues",
            ),
        ),
        (
            "Does Boeing have an improving gross margin profile as of FY2022?",
            ("Total revenues", "Total costs and expenses", "Gross profit"),
        ),
        (
            "Which debt securities are registered to trade on a national securities exchange?",
            ("Section 12(b)", "Section 12(g)", "None"),
        ),
    ),
)
def test_b3_finance_retrieval_focus_targets_authoritative_sections(
    question: str,
    required_focus: tuple[str, ...],
) -> None:
    query = retrieval_query(question, domain="finance")
    plan = build_query_plan(
        question,
        answer_type="extractive",
        verification_domain="finance",
    )

    assert all(term in query for term in required_focus)
    assert all(
        all(term in slot.query for term in required_focus)
        for slot in plan.evidence_slots
        if slot.required_for_retrieval
    )


def test_b3_wrong_page_does_not_fill_narrative_authority_or_suppress_round2() -> None:
    question = (
        "As of FY 2021, how much did Verizon expect to pay for its retirees in 2024?"
    )
    wrong_page = _page(
        "VERIZON_2021_10K#page:35",
        "35",
        "Retirees may use wireless services and other employee benefit programs.",
        source_id="VERIZON_2021_10K",
    )
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        [wrong_page],
    )

    assert plan.evidence_slots[0].status == "missing"
    assert plan.evidence_slots[0].evidence_ids == ()
    requests = missing_slot_requests(plan)
    assert len(requests) == 1
    assert requests[0]["slot_id"] == "support:primary"
