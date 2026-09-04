from __future__ import annotations

from benchmark.stage_metrics import prediction_stage_metrics


def test_finance_stage_metrics_separate_answerable_and_expected_missing_denominators():
    answerable = _prediction(
        gold_answer="20%",
        operands=[{"operand_id": "prior"}, {"operand_id": "current"}],
        valid=True,
        required=["operand:prior", "operand:current"],
        verified=["operand:prior", "operand:current"],
        errors=[],
        execution_status="ok",
    )
    expected_missing = _prediction(
        gold_answer="unanswerable",
        operands=[],
        valid=False,
        required=["operand:current"],
        verified=[],
        errors=["required_slot_missing:operand:current"],
        execution_status="error",
    )

    answerable_metrics = prediction_stage_metrics(answerable)
    missing_metrics = prediction_stage_metrics(expected_missing)

    assert answerable_metrics["answerable_all_operands_bound"] == 1.0
    assert answerable_metrics["answerable_required_slot_coverage"] == 1.0
    assert answerable_metrics["expected_missing_slot_detection"] is None
    assert missing_metrics["overall_all_operands_bound"] == 0.0
    assert missing_metrics["answerable_all_operands_bound"] is None
    assert missing_metrics["expected_missing_slot_detection"] == 1.0


def _prediction(
    *,
    gold_answer: str,
    operands: list[dict[str, str]],
    valid: bool,
    required: list[str],
    verified: list[str],
    errors: list[str],
    execution_status: str,
) -> dict[str, object]:
    return {
        "answer_type": "numeric",
        "gold_answers": [gold_answer],
        "answer_for_scoring": gold_answer,
        "evidence_metadata": {
            "query_plan": {
                "answer_type": "numeric",
                "constraints": {"verification_domain": "finance"},
            },
            "finance_numeric_trace": {
                "calculation_plan": {"operands": operands, "steps": []},
                "calculation_verification": {
                    "valid": valid,
                    "errors": errors,
                    "verified_operand_ids": [
                        item["operand_id"] for item in operands if valid
                    ],
                    "required_slot_ids": required,
                    "verified_required_slot_ids": verified,
                },
                "calculation_execution": {"status": execution_status},
            },
        },
    }
