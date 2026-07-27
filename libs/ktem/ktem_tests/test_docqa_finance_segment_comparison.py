from types import SimpleNamespace

from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer


def test_segment_comparison_binds_entity_period_matrix_before_argmax():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, excluding Embedded, in which AMD reporting "
            "segment did sales proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "segment-table",
                "text": (
                    "AMD net revenue by reporting segment (in millions)\n"
                    "2022 2021\n"
                    "Data Center 6,043 3,694\n"
                    "Client 6,201 6,887\n"
                    "Gaming 6,805 5,607\n"
                    "Embedded 4,552 246\n"
                ),
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.answer == "Data Center"
    assert result.status == "ok"
    trace = result.as_trace()
    assert trace["contract_id"] == "finance_segment_comparison.v1"
    assert trace["periods"] == ["2021", "2022"]
    assert trace["excluded_entities"] == ["Embedded"]
    assert set(trace["entity_period_values"]) == {
        "Data Center",
        "Client",
        "Gaming",
    }
    assert trace["citation_ids"] == ["segment-table"]


def test_segment_comparison_refuses_incomplete_entity_period_matrix():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "one-row",
                "text": "2022 2021\nData Center 6,043 3,694",
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.answer == ""
    assert result.status == "insufficient_entities"


def test_segment_comparison_parses_financebench_vertical_table_extraction():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, excluding Embedded, in which AMD reporting "
            "segment did sales proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "AMD_2022_10K#page:47",
                "text": (
                    "Year Ended\nDecember 31,\n2022\nDecember 25,\n2021\n"
                    "(In millions)\nNet revenue:\nData Center\n$\n6,043\n$\n"
                    "3,694\nClient\n6,201\n6,887\nGaming\n6,805\n5,607\n"
                    "Embedded\n4,552\n246\nTotal net revenue\n$\n23,601\n"
                    "$\n16,434\nOperating income (loss):\nData Center\n"
                    "$\n1,848\n$\n991"
                ),
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.status == "ok"
    assert result.answer == "Data Center"
    assert result.entity_period_values["Data Center"] == {
        "2022": "6043",
        "2021": "3694",
    }


def test_segment_comparison_does_not_overwrite_sales_with_later_table_sections():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, excluding Embedded, in which AMD reporting "
            "segment did sales proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "AMD_2022_10K#page:68",
                "text": (
                    "The following table provides net revenue and operating "
                    "income by segment.\n"
                    "Year Ended\n2022 2021\n"
                    "Net revenue:\n"
                    "Data Center 6,043 3,694\n"
                    "Client 6,201 6,887\n"
                    "Gaming 6,805 5,607\n"
                    "Embedded 4,552 246\n"
                    "Total net revenue 23,601 16,434\n"
                    "Operating income (loss):\n"
                    "Data Center 1,848 991\n"
                    "Client 1,190 2,088\n"
                    "Gaming 953 934\n"
                    "Embedded 2,084 207"
                ),
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.status == "ok"
    assert result.answer == "Data Center"
    assert result.entity_period_values["Data Center"] == {
        "2022": "6043",
        "2021": "3694",
    }
    assert "Acquisition-related Costs" not in result.entity_period_values


def test_finance_route_uses_deterministic_segment_comparison_contract():
    bundle = SimpleNamespace(
        items=[
            {
                "evidence_id": "segment-table",
                "text": (
                    "AMD net revenue by reporting segment (in millions)\n"
                    "2022 2021\nData Center 6,043 3,694\n"
                    "Client 6,201 6,887\nGaming 6,805 5,607\n"
                    "Embedded 4,552 246"
                ),
            }
        ],
        metadata={},
    )

    answer = route_finance_numeric_answer(
        SimpleNamespace(
            controller_question=(
                "From FY21 to FY22, excluding Embedded, in which AMD "
                "reporting segment did sales proportionally increase the most?"
            ),
            verification_domain="finance",
        ),
        SimpleNamespace(route="hybrid_rag"),
        bundle,
    )

    assert answer == "Data Center"
    assert bundle.metadata["generation_backend"] == "finance_comparison_answerer"
    assert bundle.metadata["finance_comparison_trace"]["status"] == "ok"
    assert "finance_numeric_trace" not in bundle.metadata
