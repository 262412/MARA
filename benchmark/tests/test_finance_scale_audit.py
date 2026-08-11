from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.contract_invariant_summary import summarize_contract_invariants
from benchmark.execution_slot_contract_metrics import required_slot_reference_metrics


def test_dimension_binding_rate_does_not_hide_missing_operand_scale_provenance() -> None:
    operand, dimension = _evidence_records()
    metadata = _metadata(
        identity_of(operand).key,
        identity_of(dimension).key,
    )
    prediction: dict[str, Any] = {
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
    }

    metrics = required_slot_reference_metrics(
        prediction,
        metadata,
        [operand, dimension],
    )

    assert metrics["dimension_binding_rate"] == 1.0
    assert metrics["effective_scale_coverage_rate"] == 0.0
    assert metrics["effective_scale_missing_count"] == 1.0
    summary = summarize_contract_invariants([metrics])
    assert summary["effective_scale_coverage_rate"] == 0.0
    assert summary["effective_scale_missing_count"] == 1.0
    prediction.update(
        {
            "example_id": "missing-effective-scale",
            "evidence_metadata": {
                **metadata,
                "selected_evidence": [operand, dimension],
            },
        }
    )
    contract_summary = contract_invariant_summary([prediction])
    assert contract_summary["effective_scale_missing_count"] == 1.0
    assert contract_summary["effective_scale_missing_unique_example_count"] == 1
    assert contract_summary["finance_contract_violation_route_count"] == 1
    assert contract_summary["finance_contract_violation_unique_example_count"] == 1


def test_operand_local_scale_is_effective_without_a_shared_dimension_slot() -> None:
    amount = {
        "evidence_id": "capacity-amount",
        "source_id": "report",
        "page_label": "2",
        "span_id": "capacity-amount",
        "evidence_level": "span",
        "value": "4200000000",
        "unit": "USD",
        "currency": "USD",
        "scale": "one",
        "scale_provenance": "local_currency_amount",
        "text": "$4,200,000,000",
    }
    amount_id = identity_of(amount).key
    metadata = {
        "query_plan": {
            "answer_type": "numeric",
            "question_type": "calculation",
            "constraints": {"verification_domain": "finance"},
            "evidence_slots": [
                {
                    "slot_id": "operand:capacity",
                    "role": "operand",
                    "required_for_execution": True,
                    "status": "filled",
                    "evidence_ids": [amount_id],
                }
            ],
        },
        "finance_numeric_trace": {
            "calculation_plan": {
                "operands": [
                    {
                        "operand_id": "capacity",
                        "query_slot_id": "operand:capacity",
                        "evidence_identity": amount_id,
                        "unit": "USD",
                        "scale": "one",
                        "scale_evidence_identity": amount_id,
                        "dimension_binding_scope": "operand_local",
                    }
                ]
            },
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": ["operand:capacity"],
            },
            "calculation_execution": {"status": "ok"},
        },
    }

    metrics = required_slot_reference_metrics(
        {
            "question": "What is the available borrowing capacity?",
            "answer_type": "numeric",
            "gold_answers": ["$4.2 billion"],
        },
        metadata,
        [amount],
    )

    assert metrics["effective_scale_coverage_rate"] == 1.0
    assert metrics["effective_scale_missing_count"] == 0.0
    assert metrics["execution_dimension_slot_count"] == 0.0


def _evidence_records() -> tuple[dict[str, Any], dict[str, Any]]:
    operand = {
        "source_id": "report",
        "page_label": "30",
        "table_id": "income",
        "cell_id": "revenue-2023",
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": "Revenue",
        "column_label": "2023",
        "period": "2023",
        "value": "120",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": "Revenue 2023 120",
    }
    dimension = {
        "source_id": "report",
        "page_label": "30",
        "table_id": "income",
        "element_id": "income-caption",
        "evidence_level": "element",
        "scale": "million",
        "text": "Consolidated statements of income, USD in millions",
    }
    return operand, dimension


def _metadata(operand_id: str, dimension_id: str) -> dict[str, Any]:
    return {
        "query_plan": {
            "answer_type": "numeric",
            "question_type": "calculation",
            "constraints": {"verification_domain": "finance"},
            "evidence_slots": [
                {
                    "slot_id": "operand:revenue:2023",
                    "role": "operand",
                    "metric": "revenue",
                    "period": "2023",
                    "statement_kind": "income_statement",
                    "financial_scope": "consolidated",
                    "required_for_execution": True,
                    "status": "filled",
                    "evidence_ids": [operand_id],
                },
                {
                    "slot_id": "dimension:scale",
                    "role": "dimension",
                    "scale": "million",
                    "required_for_execution": True,
                    "status": "filled",
                    "evidence_ids": [dimension_id],
                },
            ],
        },
        "finance_numeric_trace": {
            "calculation_plan": {
                "operands": [
                    {
                        "operand_id": "revenue_2023",
                        "query_slot_id": "operand:revenue:2023",
                        "evidence_identity": operand_id,
                        "scale": "",
                        "scale_evidence_identity": "",
                        "dimension_binding_scope": "",
                    }
                ]
            },
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": [
                    "operand:revenue:2023",
                    "dimension:scale",
                ],
            },
            "calculation_execution": {"status": "ok"},
        },
    }
