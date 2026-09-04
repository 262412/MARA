from decimal import Decimal

from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_table import parse_financial_table_cells
from ktem.docqa.query_planning import build_query_plan


def test_twelve_month_dual_period_measure_header_materializes_adjusted_ebitda() -> None:
    page = {
        "evidence_id": "amcor-page-12",
        "source_id": "amcor",
        "page_label": "1",
        "evidence_level": "page",
        "modality": "image",
        "text": (
            "Key Financials\nTwelve Months Ended June 30,\n"
            "GAAP results 2022 $ million 2023 $ million\n"
            "Net sales 14,544 14,694\nNet income 805 1,048\n"
            "EPS (diluted US cents) 52.9 70.5\n"
            "Twelve Months Ended June 30,\nReported change % Comparable "
            "constant currency change %\n"
            "Adjusted non-GAAP results 2022 $ million 2023 $ million\n"
            "Net sales 14,544 14,694 1 0\nEBITDA 2,117 2,018 (5) 1\n"
            "EBIT 1,701 1,608 (5) 1\nNet income 1,224 1,089 (11) (4)\n"
            "EPS (diluted US cents) 80.5 73.3 (9) (2)"
        ),
    }

    cells = parse_financial_table_cells(page)
    target = next(
        cell
        for cell in cells
        if cell.row_label == "Adjusted EBITDA" and cell.period == "2023"
    )

    assert target.value == Decimal("2018")
    assert target.period_kind == "fiscal_year"
    assert target.scale == "million"
    assert target.statement_kind == "non_gaap_performance"

    question = "What was AMCOR's Adjusted Non GAAP EBITDA for FY2023?"
    answer = finance_numeric_answer(
        question,
        [page],
        query_plan=build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ).as_dict(),
    )

    assert answer is not None
    assert answer.answer == "$2,018 million"
