from ktem.docqa.finance_numeric_answer import finance_numeric_answer


def test_finance_direct_fact_binds_fiscal_cell_not_quarterly_cell():
    answer = finance_numeric_answer(
        "What was AMCOR's adjusted non-GAAP EBITDA for FY2023?",
        [
            _ebitda_cell(
                "quarter-ebitda",
                "quarter-table",
                "quarter",
                "540",
                "Three Months Ended",
            ),
            _ebitda_cell(
                "fiscal-ebitda",
                "fiscal-table",
                "fiscal_year",
                "2018",
                "Twelve Months Ended",
            ),
        ],
    )

    assert answer is not None
    assert answer.answer == "$2,018 million"
    assert answer.calculation_verification["valid"] is True
    [operand] = answer.calculation_plan["operands"]
    assert operand["cell_id"] == "fiscal-ebitda"
    assert operand["value"] == "2018"
    assert operand["period_kind"] == "fiscal_year"


def _ebitda_cell(
    evidence_id: str,
    table_id: str,
    period_kind: str,
    value: str,
    heading: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "element_id": table_id,
        "table_id": table_id,
        "cell_id": evidence_id,
        "evidence_level": "cell",
        "modality": "table",
        "row_label": "Adjusted EBITDA",
        "column_label": "2023",
        "period": "2023",
        "period_kind": period_kind,
        "value": value,
        "scale": "million",
        "text": f"{heading} Adjusted EBITDA 2023 {value} million",
    }
