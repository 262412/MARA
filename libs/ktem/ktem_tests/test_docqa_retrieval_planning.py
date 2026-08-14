from time import monotonic
from types import SimpleNamespace

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.retrieval_rounds import retrieve_with_rounds


@pytest.mark.parametrize(
    ("prompt", "answer_type"),
    [
        ("What was the percentage change from 2021 to 2022?", "numeric"),
        ("Compare the table across pages.", "free_text"),
        ("What does the chart show?", "free_text"),
    ],
)
def test_auto_policy_routes_high_risk_questions_to_hybrid(prompt, answer_type):
    payload = build_controller_outputs(
        DocQARequest(
            prompt=prompt,
            task_type=answer_type,
            route_policy="auto",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "evidence-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": prompt,
                }
            ]
        },
    )

    assert payload["route_decision"]["route"] == "hybrid"
    assert "risk" in payload["route_decision"]["reason"].lower()


def test_auto_policy_uses_controller_question_instead_of_generation_contract():
    payload = build_controller_outputs(
        DocQARequest(
            prompt=(
                "Benchmark gold-answer contract: inspect every table, compare all "
                "pages, and calculate a percentage.\nQuestion: Who is the chair?"
            ),
            controller_question="Who is the chair?",
            retrieval_query="Who is the chair?",
            task_type="free_text",
            route_policy="auto",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "evidence-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "The chair is Ada.",
                }
            ]
        },
    )

    assert payload["route_decision"]["route"] == "doc_text"
    assert payload["evidence_bundle"]["metadata"]["query_plan"]["subqueries"] == [
        "Who is the chair?"
    ]


def test_second_round_targets_only_missing_evidence_slot():
    queries = []

    def retrieve(request, _decision):
        queries.append(request.retrieval_query)
        if len(queries) == 1:
            return {"evidence": [_revenue_cell("revenue-2021", "2021", "10")]}
        return {"evidence": [_revenue_cell("revenue-2022", "2022", "12")]}

    def generate(_request, _decision, bundle):
        assert {item["evidence_id"] for item in bundle.items} == {
            "revenue-2021",
            "revenue-2022",
        }
        return "20%."

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the percentage change in revenue from 2021 to 2022?",
            retrieval_query="percentage change revenue 2021 2022",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert len(queries) == 2
    assert queries[1] == "revenue consolidated statements of income 2022"
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 1
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0


def test_second_round_retrieves_each_missing_slot_independently():
    queries = []

    def retrieve(request, _decision):
        queries.append((request.retrieval_query, request.retrieval_slot_id))
        if len(queries) == 1:
            return {
                "evidence": [
                    _finance_cell(
                        "current-assets",
                        "Current assets",
                        "100",
                    )
                ]
            }
        if request.retrieval_slot_id.endswith("current_liabilities"):
            return {
                "evidence": [
                    _finance_cell(
                        "current-liabilities",
                        "Current liabilities",
                        "50",
                    )
                ]
            }
        return {
            "evidence": [
                _finance_cell(
                    "inventories",
                    "Inventories",
                    "10",
                )
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the quick ratio in FY2023?",
            retrieval_query="quick ratio FY2023",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
        ),
        retrieve=retrieve,
        generate=lambda *_args: "1.8",
    )

    assert len(queries) == 3
    assert {slot_id for _query, slot_id in queries[1:]} == {
        "operand:current_liabilities",
        "operand:inventory",
    }
    assert all("\n" not in query for query, _slot_id in queries[1:])
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 1
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0
    lineage_by_id = {
        item["evidence_id"]: item["retrieval_lineage"]
        for item in result.evidence_bundle.metadata["candidate_evidence"]
    }
    assert lineage_by_id["current-assets"] == [
        {
            "round_id": 1,
            "query_id": "round1:operand:current_assets",
            "slot_id": "operand:current_assets",
            "retriever_name": "text",
            "raw_rank": 1,
            "raw_score": None,
            "score_type": "not_recorded",
        }
    ]
    assert lineage_by_id["current-liabilities"][0]["slot_id"] == (
        "operand:current_liabilities"
    )
    assert lineage_by_id["current-liabilities"][0]["round_id"] == 1


def test_quality_retry_query_is_never_empty():
    queries = []

    def retrieve(request, _decision):
        queries.append(request.retrieval_query)
        return {
            "evidence": [
                {
                    "evidence_id": "ambiguous-evidence",
                    "source_id": "paper",
                    "page_label": "4",
                    "text": "The comparison is discussed in the results.",
                }
            ]
        }

    def evaluate(*_args, attempted_retry, **_kwargs):
        return SimpleNamespace(
            status="good" if attempted_retry else "ambiguous",
            retry=not attempted_retry,
        )

    request = DocQARequest(
        prompt="Which method performed better?",
        retrieval_query="   ",
        route_policy="doc",
    )
    retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=evaluate,
        retry_poor=False,
    )

    assert queries == [
        "Which method performed better?",
        "Which method performed better?",
    ]
    assert all(query.strip() for query in queries)


def test_missing_required_slot_after_second_round_blocks_generation():
    calls = []

    def retrieve(_request, _decision):
        calls.append(1)
        return {
            "evidence": [
                _finance_cell(
                    "current-assets",
                    "Current assets",
                    "100",
                )
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the quick ratio in FY2023?",
            retrieval_query="quick ratio FY2023",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
            allowed_routes=["doc_text"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("missing required slots must block generation")
        ),
    )

    assert len(calls) == 5
    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"


def _finance_cell(evidence_id, row_label, value):
    return {
        "evidence_id": evidence_id,
        "file_id": "report",
        "page_label": "4",
        "element_id": "balance-sheet",
        "table_id": "balance-sheet",
        "cell_id": evidence_id,
        "evidence_level": "cell",
        "row_label": row_label,
        "column_label": "2023",
        "period": "2023",
        "period_kind": "fiscal_year",
        "statement_kind": "balance_sheet",
        "financial_scope": "consolidated",
        "value": value,
        "scale": "million",
        "modality": "table",
        "text": f"{row_label} 2023 {value} million",
    }


def _revenue_cell(evidence_id: str, period: str, value: str):
    return {
        "evidence_id": evidence_id,
        "file_id": "file-1",
        "page_label": period,
        "element_id": "revenue-table",
        "table_id": "revenue-table",
        "cell_id": evidence_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": "Revenue",
        "column_label": period,
        "period": period,
        "value": value,
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "modality": "table",
        "text": f"Revenue {period} {value}",
    }


def test_second_round_retrieves_missing_same_source_scale_convention():
    queries = []

    def retrieve(request, _decision):
        queries.append(request.retrieval_query)
        if len(queries) == 1:
            return {
                "evidence": [
                    {
                        "evidence_id": "pepsico-capex",
                        "file_id": "pepsico",
                        "page_label": "53",
                        "element_id": "cash-flow-table",
                        "table_id": "cash-flow-table",
                        "evidence_level": "element",
                        "modality": "table",
                        "text": (
                            "Consolidated Statement of Cash Flows\n"
                            "2021 2020\nCapital spending (4,625) (4,240)"
                        ),
                    }
                ]
            }
        return {
            "evidence": [
                {
                    "evidence_id": "pepsico-scale",
                    "file_id": "pepsico",
                    "page_label": "40",
                    "text": (
                        "Unless otherwise noted, tabular dollars are "
                        "presented in millions."
                    ),
                }
            ]
        }

    def generate(request, _decision, bundle):
        result = finance_numeric_answer(
            request.prompt,
            bundle.items,
            query_plan=bundle.metadata["query_plan"],
        )
        assert result is not None
        assert result.answer == "$4.6 billion"
        return result.answer

    result = execute_controller_turn(
        DocQARequest(
            prompt="What is FY2021 capital expenditure in USD billions?",
            controller_question=("What is FY2021 capital expenditure in USD billions?"),
            retrieval_query="FY2021 capital expenditure",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert queries == [
        "capital expenditure capital spending consolidated statement of cash flows 2021",
        (
            "tabular dollars unit scale convention capital expenditure 2021 "
            "capital expenditure capital spending consolidated statement of cash "
            "flows 2021"
        ),
    ]
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 1
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0


def test_expired_route_deadline_stops_before_first_retrieval():
    calls = []

    def retrieve(_request, _decision):
        calls.append(1)
        return {
            "evidence": [
                {
                    "evidence_id": "revenue-2021",
                    "file_id": "file-1",
                    "page_label": "4",
                    "text": "Revenue was $10 million in 2021.",
                }
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the percentage change in revenue from 2021 to 2022?",
            retrieval_query="percentage change revenue 2021 2022",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
            route_deadline_monotonic=monotonic() - 1,
        ),
        retrieve=retrieve,
        generate=lambda *_args: "20%.",
    )

    assert calls == []
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.reason == "route_deadline_exhausted"
