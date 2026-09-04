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


def test_verifier_rejects_page_level_operand_with_multiple_candidate_values():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="capex",
                evidence_id="page-17",
                value=Decimal("3215.4"),
                period="2022",
                unit="million",
                scale="million",
            ),
        ),
        steps=(),
        result_step_id="capex",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {
                "evidence_id": "page-17",
                "evidence_level": "page",
                "modality": "table",
                "text": (
                    "2022 2021\nOperating cash flow 3,676.2 3,100.0\n"
                    "Capital expenditures 460.8 420.0\n"
                    "Free cash flow 3,215.4 2,680.0"
                ),
            }
        ],
        question="What was free cash flow in FY2022?",
    )

    assert not verification.valid
    assert "operand_atomic_binding_missing:capex" in verification.errors


def test_verifier_rejects_every_page_level_operand_without_atomic_identity():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="assets",
                evidence_id="page-52",
                value=Decimal("20000"),
                period="2019",
                scale="million",
            ),
        ),
        steps=(),
        result_step_id="assets",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {
                "evidence_id": "page-52",
                "evidence_level": "page",
                "text": "Total current assets were 20,000 million in 2019.",
            }
        ],
        question="What were total current assets in FY2019?",
    )

    assert not verification.valid
    assert "operand_atomic_binding_missing:assets" in verification.errors


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


def test_required_slots_bind_semantically_to_final_selected_evidence():
    selected_evidence = {
        "evidence_id": "selected-page-2",
        "source_id": "PEPSICO_2023_10K",
        "page_label": "2",
        "text": (
            "In 2023, two revolving credit agreements each enable PepsiCo "
            "to borrow up to USD $4.2 billion."
        ),
    }
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="agreement_1",
                evidence_id="selected-page-2",
                value=Decimal("4.2"),
                period="2023",
                unit="USD",
                scale="billion",
                currency="USD",
            ),
            CalculationOperand(
                operand_id="agreement_2",
                evidence_id="selected-page-2",
                value=Decimal("4.2"),
                period="2023",
                unit="USD",
                scale="billion",
                currency="USD",
            ),
        ),
        steps=(
            CalculationStep(
                step_id="result",
                operator="add",
                input_ids=("agreement_1", "agreement_2"),
            ),
        ),
        result_step_id="result",
        answer_unit="USD",
        answer_scale="billion",
    )
    slots = [
        {
            "slot_id": f"operand:revolving_credit_capacity:{index}",
            "role": "operand",
            "metric": "revolving credit capacity",
            "period": "2023",
            "required": True,
            "status": "missing",
            "evidence_ids": ["preliminary-page-85"],
        }
        for index in (1, 2)
    ]

    verification = verify_calculation_plan(
        plan,
        [selected_evidence],
        question="What was the total revolving credit capacity in 2023?",
        required_slots=slots,
    )

    assert verification.valid is True
    assert verification.verified_required_slot_ids == (
        "operand:revolving_credit_capacity:1",
        "operand:revolving_credit_capacity:2",
    )


def test_required_slot_rejects_inventory_change_as_inventory_balance():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="inventory_2018",
                evidence_id="cash-flow-inventory-change",
                value=Decimal("251"),
                period="2018",
                unit="USD",
                scale="million",
                currency="USD",
                row_label="Inventories",
            ),
        ),
        steps=(),
        result_step_id="inventory_2018",
        answer_unit="USD",
        answer_scale="million",
    )

    verification = verify_calculation_plan(
        plan,
        [
            {
                "evidence_id": "cash-flow-inventory-change",
                "text": (
                    "Consolidated Statements of Cash Flows (in millions). "
                    "Changes in current assets and liabilities. "
                    "Inventories (277) (251). 2019 2018."
                ),
            }
        ],
        question="What was the inventory balance in FY2018?",
        required_slots=[
            {
                "slot_id": "operand:inventory:2018",
                "role": "operand",
                "metric": "inventory",
                "period": "2018",
                "required": True,
                "status": "filled",
            }
        ],
    )

    assert verification.valid is False
    assert "required_slot_missing:operand:inventory:2018" in verification.errors


def test_required_slot_semantic_binding_still_rejects_wrong_metric():
    plan = CalculationPlan(
        operands=(
            _operand(
                "pension",
                "selected-pension",
                "4.2",
                period="2023",
                unit="USD",
            ),
        ),
        steps=(),
        result_step_id="pension",
        answer_unit="USD",
        answer_scale="billion",
    )

    verification = verify_calculation_plan(
        plan,
        [
            {
                "evidence_id": "selected-pension",
                "text": "Pension expense was USD $4.2 billion in 2023.",
            }
        ],
        question="What was the revolving credit capacity in 2023?",
        required_slots=[
            {
                "slot_id": "operand:revolving_credit_capacity:2023",
                "role": "operand",
                "metric": "revolving credit capacity",
                "period": "2023",
                "required": True,
                "status": "filled",
                "evidence_ids": ["preliminary-page-85"],
            }
        ],
    )

    assert verification.valid is False
    assert (
        "required_slot_missing:operand:revolving_credit_capacity:2023"
        in verification.errors
    )


def test_required_slot_binding_rejects_scattered_metric_tokens():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="cost_of_goods_sold",
                evidence_id="pension-distractor",
                value=Decimal("7"),
                unit="USD",
                scale="million",
                currency="USD",
                period="2018",
            ),
        ),
        steps=(),
        result_step_id="cost_of_goods_sold",
        answer_unit="USD",
        answer_scale="million",
    )

    verification = verify_calculation_plan(
        plan,
        [
            {
                "evidence_id": "pension-distractor",
                "text": (
                    "In 2018 compensation cost was USD $7 million. Finished "
                    "goods were discussed, and unrelated assets were sold."
                ),
            }
        ],
        question="What was cost of goods sold in 2018?",
        required_slots=[
            {
                "slot_id": "operand:cost_of_goods_sold:2018",
                "role": "operand",
                "metric": "cost of goods sold",
                "period": "2018",
                "required": True,
                "status": "filled",
                "evidence_ids": ["preliminary-candidate"],
            }
        ],
    )

    assert verification.valid is False
    assert (
        "required_slot_missing:operand:cost_of_goods_sold:2018" in verification.errors
    )


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


def test_verifier_rejects_missing_scale_when_peer_operand_has_explicit_scale():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="value_2017",
                evidence_id="cell-2017",
                value=Decimal("46"),
                scale="thousand",
                period="2017",
            ),
            CalculationOperand(
                operand_id="value_2018",
                evidence_id="cell-2018",
                value=Decimal("4"),
                period="2018",
            ),
        ),
        steps=(
            CalculationStep(
                step_id="result",
                operator="average",
                input_ids=("value_2017", "value_2018"),
            ),
        ),
        result_step_id="result",
        answer_unit="percent",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {
                "evidence_id": "cell-2017",
                "text": "An unrelated value was 46 thousand in 2017.",
            },
            {
                "evidence_id": "cell-2018",
                "text": "An unrelated value was 4 in 2018.",
            },
        ],
        question="What was the average percentage from 2017 to 2018?",
    )

    assert not verification.valid
    assert "scale_mismatch:result" in verification.errors


def test_verifier_rejects_period_bound_as_operand_value():
    plan = CalculationPlan(
        operands=(
            CalculationOperand(
                operand_id="value",
                evidence_id="credit-agreement",
                value=Decimal("2023"),
                period="2023",
            ),
        ),
        steps=(),
        result_step_id="value",
    )

    verification = verify_calculation_plan(
        plan,
        evidence_items=[
            {
                "evidence_id": "credit-agreement",
                "text": (
                    "On May 26, 2023, the company entered into a revolving "
                    "credit agreement of $4.2 billion."
                ),
            }
        ],
        question="What amount was available under the agreement in 2023?",
    )

    assert not verification.valid
    assert "operand_value_is_period:value" in verification.errors


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
