from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.contract_invariant_summary import summarize_contract_invariants
from benchmark.execution_slot_contract_metrics import required_slot_reference_metrics


def test_dimension_evidence_is_not_a_failed_atomic_operand_slot() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(operand_id, dimension_id)
    prediction = {
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
    }

    metrics = required_slot_reference_metrics(
        prediction,
        metadata,
        [operand, dimension],
    )

    assert metrics["execution_operand_slot_count"] == 1.0
    assert metrics["execution_dimension_slot_count"] == 1.0
    assert metrics["execution_slot_atomicity_violation_count"] == 0.0
    assert metrics["parent_table_false_fill_count"] == 0.0
    assert metrics["dimension_binding_violation_count"] == 0.0
    assert metrics["dimension_scope_violation_count"] == 0.0
    summary = summarize_contract_invariants([metrics])
    assert summary["execution_operand_slot_count"] == 1.0
    assert summary["execution_dimension_slot_count"] == 1.0
    assert summary["dimension_binding_violation_count"] == 0.0
    assert summary["dimension_scope_violation_count"] == 0.0


def _evidence_records() -> tuple[dict[str, Any], dict[str, Any]]:
    operand = {
        "source_id": "report",
        "page_label": "12",
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
        "page_label": "12",
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
            "constraints": {
                "verification_domain": "finance",
                "requires_structure": True,
            },
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
                        "evidence_identity": operand_id,
                    }
                ]
            }
        },
    }
