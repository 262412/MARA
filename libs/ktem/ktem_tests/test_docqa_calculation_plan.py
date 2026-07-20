from decimal import Decimal

from ktem.docqa.calculation_plan import (
    CalculationOperand,
    CalculationPlan,
    CalculationStep,
    execute_calculation_plan,
    verify_calculation_plan,
)


def test_percent_change_uses_decimal_and_collects_all_operand_citations():
    plan = CalculationPlan(
        operands=(
            _operand("prior", "cell-2021", "10", period="2021"),
            _operand("current", "cell-2022", "12.5", period="2022"),
        ),
        steps=(
            CalculationStep(
                step_id="result",
                operator="percent_change",
                input_ids=("prior", "current"),
            ),
        ),
        result_step_id="result",
        answer_unit="percent",
    )

    result = execute_calculation_plan(plan)

    assert result.status == "ok"
    assert result.value == Decimal("25.00")
    assert result.citation_ids == ("cell-2021", "cell-2022")


def test_verifier_rejects_operand_without_traceable_evidence_cell():
    plan = CalculationPlan(
        operands=(_operand("assets", "missing-cell", "14688"),),
        steps=(),
        result_step_id="assets",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {"evidence_id": "different-cell", "text": "Assets were 14,688."}
        ],
        question="What were assets?",
    )

    assert not verification.valid
    assert "operand_evidence_missing:assets" in verification.errors


def test_verifier_rejects_period_and_unit_mismatch():
    plan = CalculationPlan(
        operands=(
            _operand(
                "revenue",
                "cell-1",
                "12.5",
                period="2022",
                unit="million",
                currency="USD",
            ),
        ),
        steps=(),
        result_step_id="revenue",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {
                "evidence_id": "cell-1",
                "text": "Revenue was EUR 12.5 billion in 2021.",
            }
        ],
        question="What was revenue in 2022 in USD millions?",
    )

    assert not verification.valid
    assert "operand_period_mismatch:revenue" in verification.errors
    assert "operand_unit_mismatch:revenue" in verification.errors
    assert "operand_currency_mismatch:revenue" in verification.errors


def test_execute_rejects_zero_division_without_guessing():
    plan = CalculationPlan(
        operands=(
            _operand("numerator", "cell-a", "10"),
            _operand("denominator", "cell-b", "0"),
        ),
        steps=(
            CalculationStep(
                step_id="result",
                operator="divide",
                input_ids=("numerator", "denominator"),
            ),
        ),
        result_step_id="result",
    )

    result = execute_calculation_plan(plan)

    assert result.status == "error"
    assert result.error == "division_by_zero:result"
    assert result.value is None


def test_verifier_rejects_unsupported_operator_and_unbound_input():
    plan = CalculationPlan(
        operands=(_operand("value", "cell-a", "10"),),
        steps=(
            CalculationStep(
                step_id="result",
                operator="python_eval",
                input_ids=("not-bound",),
            ),
        ),
        result_step_id="result",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[{"evidence_id": "cell-a", "text": "Value was 10."}],
        question="Calculate the value.",
    )

    assert not verification.valid
    assert "unsupported_operator:result" in verification.errors
    assert "unbound_step_input:result:not-bound" in verification.errors


def _operand(
    operand_id,
    evidence_id,
    value,
    *,
    period="",
    unit="million",
    currency="USD",
):
    return CalculationOperand(
        operand_id=operand_id,
        evidence_id=evidence_id,
        value=Decimal(value),
        unit=unit,
        scale="million",
        currency=currency,
        period=period,
        entity="Example Corp",
    )
