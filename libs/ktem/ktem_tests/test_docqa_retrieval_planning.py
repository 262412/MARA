from time import monotonic

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.finance_numeric_answer import finance_numeric_answer


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
            return {
                "evidence": [
                    {
                        "evidence_id": "revenue-2021",
                        "file_id": "file-1",
                        "page_label": "4",
                        "element_id": "revenue-table-2021",
                        "table_id": "revenue-table-2021",
                        "evidence_level": "element",
                        "modality": "table",
                        "text": "Revenue was $10 million in 2021.",
                    }
                ]
            }
        return {
            "evidence": [
                {
                    "evidence_id": "revenue-2022",
                    "file_id": "file-1",
                    "page_label": "5",
                    "element_id": "revenue-table-2022",
                    "table_id": "revenue-table-2022",
                    "evidence_level": "element",
                    "modality": "table",
                    "text": "Revenue was $12 million in 2022.",
                }
            ]
        }

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
    assert queries[1] == "revenue 2022"
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 2
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
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 2
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0
    lineage_by_id = {
        item["evidence_id"]: item["retrieval_lineage"]
        for item in result.evidence_bundle.metadata["candidate_evidence"]
    }
    assert lineage_by_id["current-assets"] == [
        {
            "round_id": 1,
            "query_id": "round1:primary",
            "slot_id": "",
            "retriever_name": "text",
            "raw_rank": 1,
            "raw_score": None,
            "score_type": "not_recorded",
        }
    ]
    assert lineage_by_id["current-liabilities"][0]["slot_id"] == (
        "operand:current_liabilities"
    )
    assert lineage_by_id["current-liabilities"][0]["round_id"] == 2


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

    assert len(calls) == 3
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
        assert result.answer == "$4.625 billion"
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
        "FY2021 capital expenditure",
        "tabular dollars unit scale convention",
    ]
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 2
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0


def test_second_round_stops_when_generation_reserve_is_exhausted():
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

    assert calls == [1]
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 1
    assert (
        result.evidence_bundle.metadata["second_round_skipped_reason"]
        == "insufficient_remaining_time"
    )
