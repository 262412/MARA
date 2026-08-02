from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.contract_invariant_metrics import contract_invariant_summary
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


def test_verified_execution_slot_accepts_equivalent_materialized_cell() -> None:
    selected_operand, dimension = _evidence_records()
    execution_operand = {
        **selected_operand,
        "table_id": "income-materialized",
        "table_instance_id": "income-materialized",
        "cell_id": "revenue-2023-materialized",
        "materialization_source_id": "income",
    }
    selected_id = identity_of(selected_operand).key
    execution_id = identity_of(execution_operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(selected_id, dimension_id)
    finance_trace = metadata["finance_numeric_trace"]
    finance_trace["calculation_plan"]["operands"][0]["evidence_identity"] = execution_id
    finance_trace["calculation_verification"] = {
        "valid": True,
        "errors": [],
        "required_slot_ids": ["operand:revenue:2023"],
        "verified_required_slot_ids": ["operand:revenue:2023"],
    }
    finance_trace["calculation_execution"] = {"status": "ok"}
    prediction = {
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
    }

    metrics = required_slot_reference_metrics(
        prediction,
        metadata,
        [selected_operand, execution_operand, dimension],
    )

    assert metrics["execution_operand_resolution_rate"] == 1.0


def test_unique_example_violations_are_not_multiplied_by_routes() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    predictions = []
    for route in ("controller", "text-only", "hybrid"):
        metadata = _metadata(operand_id, dimension_id)
        dimension_slot = metadata["query_plan"]["evidence_slots"][1]
        dimension_slot["status"] = "missing"
        dimension_slot["evidence_ids"] = []
        predictions.append(
            {
                "example_id": "finance-example",
                "route": route,
                "question": "What was revenue in 2023, in millions?",
                "answer_type": "numeric",
                "gold_answers": ["120"],
                "evidence_metadata": {
                    **metadata,
                    "selected_evidence": [operand, dimension],
                },
            }
        )

    summary = contract_invariant_summary(predictions)

    assert summary["dimension_binding_violation_count"] == 3.0
    assert summary["dimension_binding_violation_unique_example_count"] == 1
    assert summary["finance_contract_violation_route_count"] == 3
    assert summary["finance_contract_violation_unique_example_count"] == 1


def test_query_plan_calculation_plan_state_mismatch_is_reported() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(operand_id, dimension_id)
    metadata["finance_numeric_trace"].update(
        {
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": [
                    "operand:revenue:2023",
                    "dimension:scale",
                ],
            },
            "calculation_execution": {"status": "ok"},
        }
    )
    metadata["finance_numeric_trace"]["calculation_plan"]["operands"][0].update(
        {
            "query_slot_id": "operand:revenue:2023",
            "scale": "million",
            "scale_evidence_identity": dimension_id,
        }
    )
    metadata["query_plan"]["evidence_slots"][1]["status"] = "missing"
    metadata["query_plan"]["evidence_slots"][1]["evidence_ids"] = []
    prediction = {
        "example_id": "finance-example",
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
        "evidence_metadata": {
            **metadata,
            "selected_evidence": [operand, dimension],
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["query_plan_calculation_plan_state_mismatch_count"] == 1.0
    assert (
        summary["query_plan_calculation_plan_state_mismatch_unique_example_count"] == 1
    )


def test_synchronized_query_and_calculation_plans_have_no_state_mismatch() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(operand_id, dimension_id)
    metadata["query_plan"]["state_authority"] = "verified_calculation_plan"
    metadata["query_plan"]["evidence_slots"][0].update(
        {
            "source_id": "report",
            "table_instance_id": "income",
            "table_group_id": "income",
            "scale": "million",
        }
    )
    metadata["finance_numeric_trace"].update(
        {
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": ["operand:revenue:2023"],
            },
            "calculation_execution": {"status": "ok"},
        }
    )
    metadata["finance_numeric_trace"]["calculation_plan"]["operands"][0].update(
        {
            "query_slot_id": "operand:revenue:2023",
            "source_id": "report",
            "table_instance_id": "income",
            "table_group_id": "income",
            "scale": "million",
            "scale_evidence_identity": dimension_id,
        }
    )
    prediction = {
        "example_id": "finance-example",
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
        "evidence_metadata": {
            **metadata,
            "selected_evidence": [operand, dimension],
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["query_plan_calculation_plan_state_mismatch_count"] == 0.0


def test_synchronized_verified_dimension_is_not_treated_as_an_operand() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(operand_id, dimension_id)
    metadata["query_plan"]["state_authority"] = "verified_calculation_plan"
    metadata["query_plan"]["evidence_slots"][0].update(
        {
            "source_id": "report",
            "table_instance_id": "income",
            "table_group_id": "income",
            "scale": "million",
        }
    )
    metadata["finance_numeric_trace"].update(
        {
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": [
                    "operand:revenue:2023",
                    "dimension:scale",
                ],
            },
            "calculation_execution": {"status": "ok"},
        }
    )
    metadata["finance_numeric_trace"]["calculation_plan"]["operands"][0].update(
        {
            "query_slot_id": "operand:revenue:2023",
            "source_id": "report",
            "table_instance_id": "income",
            "table_group_id": "income",
            "scale": "million",
            "scale_evidence_identity": dimension_id,
        }
    )
    prediction = {
        "example_id": "finance-example",
        "question": "What was revenue in 2023, in millions?",
        "answer_type": "numeric",
        "gold_answers": ["120"],
        "evidence_metadata": {
            **metadata,
            "selected_evidence": [operand, dimension],
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["query_plan_calculation_plan_state_mismatch_count"] == 0.0


def test_verified_execution_gold_discrepancy_is_reported_without_rescoring() -> None:
    operand, dimension = _evidence_records()
    operand_id = identity_of(operand).key
    dimension_id = identity_of(dimension).key
    metadata = _metadata(operand_id, dimension_id)
    metadata["query_plan"]["state_authority"] = "verified_calculation_plan"
    metadata["finance_numeric_trace"].update(
        {
            "answer": "$4.625 billion",
            "calculation_verification": {
                "valid": True,
                "verified_required_slot_ids": ["operand:revenue:2023"],
            },
            "calculation_execution": {"status": "ok", "value": "4.625"},
        }
    )
    prediction = {
        "example_id": "finance-example",
        "question": "What was capital spending in billions?",
        "answer_type": "numeric",
        "gold_answers": ["$4.60 billion"],
        "answer_for_scoring": "$4.625 billion",
        "evidence_metadata": {
            **metadata,
            "selected_evidence": [operand, dimension],
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["verified_execution_gold_discrepancy_count"] == 1.0
    assert summary["verified_execution_gold_discrepancy_unique_example_count"] == 1
    assert prediction.get("metrics") is None


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
