from decimal import Decimal

from ktem.docqa.finance_calculation_adapter import finance_calculation_audit


def test_adapter_uses_bound_cell_value_instead_of_unbound_candidate_value():
    evidence = [
        _cell(
            "operating-cash-flow",
            "Net cash provided by operating activities",
            "3676.2",
        ),
        _cell("capital-expenditure", "Capital expenditures", "460.8"),
    ]

    audit = finance_calculation_audit(
        "What was FY2020 free cash flow in USD millions?",
        evidence,
        question_type="free_cash_flow",
        inputs={
            "operating_cash_flow": 3676.2,
            "capital_expenditure": 3215.4,
        },
    )

    operands = {operand.operand_id: operand for operand in audit.plan.operands}
    assert operands["capital_expenditure"].value == Decimal("460.8")
    assert operands["capital_expenditure"].cell_id == "capital-expenditure"
    assert audit.verification.valid is True
    assert audit.execution.status == "ok"
    assert audit.execution.value == Decimal("3215.4")


def test_adapter_rejects_ambiguous_semantic_fallback_after_exact_value_miss():
    evidence = [
        {
            **_cell("sales-a", "Net sales", "100"),
            "element_id": "income-table-a",
            "table_id": "income-table-a",
            "table_instance_id": "income-table-a",
            "table_group_id": "income-table-a",
        },
        {
            **_cell("sales-b", "Net sales", "200"),
            "element_id": "income-table-b",
            "table_id": "income-table-b",
            "table_instance_id": "income-table-b",
            "table_group_id": "income-table-b",
        },
    ]

    audit = finance_calculation_audit(
        "What were FY2020 net sales?",
        evidence,
        question_type="net_sales",
        inputs={"net_sales_2020": 999.0},
    )

    [operand] = audit.plan.operands
    assert operand.evidence_id == ""
    assert audit.verification.valid is False
    assert "operand_evidence_missing:net_sales_2020" in audit.verification.errors


def _cell(evidence_id: str, row_label: str, value: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "element_id": "cash-flow-table",
        "table_id": "cash-flow-table",
        "cell_id": evidence_id,
        "evidence_level": "cell",
        "modality": "table",
        "row_label": row_label,
        "column_label": "2020",
        "period": "2020",
        "value": value,
        "scale": "million",
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
        "text": f"{row_label} 2020 {value} million",
    }
