from decimal import Decimal

from ktem.docqa.calculation_plan import (
    CalculationOperand,
    CalculationPlan,
    verify_calculation_plan,
)
from ktem.docqa.evidence_identity import identity_of


def test_required_dimension_slot_is_verified():
    value_evidence = {
        "evidence_id": "capital-expenditure-2021",
        "source_id": "report",
        "evidence_level": "span",
        "text": "Capital expenditure 2021 4,625.",
    }
    scale_evidence = {
        "evidence_id": "scale-convention",
        "source_id": "report",
        "text": "Unless otherwise noted, tabular dollars are in millions.",
    }
    scale_identity = "evidence:report:scale-convention"
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="capital_expenditure",
                evidence_id="capital-expenditure-2021",
                value=Decimal("4625"),
                period="2021",
                scale="million",
                scale_evidence_id="scale-convention",
                scale_evidence_identity=scale_identity,
            ),
        ),
        steps=(),
        result_step_id="capital_expenditure",
        answer_scale="billion",
    )

    verification = verify_calculation_plan(
        plan,
        [value_evidence, scale_evidence],
        question="What was FY2021 capital expenditure in USD billions?",
        required_slots=[
            {
                "slot_id": "dimension:scale",
                "role": "dimension",
                "required_for_execution": True,
                "status": "filled",
                "evidence_ids": [scale_identity],
            }
        ],
    )

    assert verification.valid is True
    assert verification.required_slot_ids == ("dimension:scale",)
    assert verification.verified_required_slot_ids == ("dimension:scale",)


def test_missing_dimension_slot_blocks_execution_verification():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="capital_expenditure",
                evidence_id="capital-expenditure-2021",
                value=Decimal("4625"),
                period="2021",
                scale="million",
            ),
        ),
        steps=(),
        result_step_id="capital_expenditure",
        answer_scale="billion",
    )

    verification = verify_calculation_plan(
        plan,
        [
            {
                "evidence_id": "capital-expenditure-2021",
                "source_id": "report",
                "evidence_level": "span",
                "text": "Capital expenditure 2021 4,625 million.",
            }
        ],
        question="What was FY2021 capital expenditure in USD billions?",
        required_slots=[
            {
                "slot_id": "dimension:scale",
                "role": "dimension",
                "required_for_execution": True,
                "status": "missing",
                "evidence_ids": [],
            }
        ],
    )

    assert verification.valid is False
    assert verification.required_slot_ids == ("dimension:scale",)
    assert "required_slot_missing:dimension:scale" in verification.errors


def test_required_operand_slots_cannot_reuse_one_physical_evidence_identity():
    cell = {
        "evidence_id": "sales-2021",
        "source_id": "report",
        "evidence_level": "cell",
        "cell_role": "data",
        "cell_id": "sales-2021",
        "row_label": "Net sales",
        "column_label": "2021",
        "period": "2021",
        "value": "100",
        "text": "Net sales 2021 100 million",
    }
    evidence_identity = identity_of(cell).key
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="revenue_a",
                evidence_id="sales-2021",
                evidence_identity=evidence_identity,
                value=Decimal("100"),
                query_slot_id="operand:revenue_a:2021",
                period="2021",
                row_label="Net sales",
            ),
            CalculationOperand(
                operand_id="revenue_b",
                evidence_id="sales-2021",
                evidence_identity=evidence_identity,
                value=Decimal("100"),
                query_slot_id="operand:revenue_b:2021",
                period="2021",
                row_label="Net sales",
            ),
        ),
        steps=(),
        result_step_id="revenue_a",
    )

    verification = verify_calculation_plan(
        plan,
        [cell],
        question="What were FY2021 net sales and the comparison value?",
        required_slots=[
            {
                "slot_id": "operand:revenue_a:2021",
                "role": "operand",
                "required_for_execution": True,
                "metric": "net sales",
                "period": "2021",
                "evidence_ids": [evidence_identity],
            },
            {
                "slot_id": "operand:revenue_b:2021",
                "role": "operand",
                "required_for_execution": True,
                "metric": "net sales",
                "period": "2021",
                "evidence_ids": [evidence_identity],
            },
        ],
    )

    assert verification.valid is False
    assert "required_slot_missing:operand:revenue_b:2021" in verification.errors
