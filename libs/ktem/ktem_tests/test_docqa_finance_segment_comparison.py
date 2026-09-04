from types import SimpleNamespace

from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan
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


def test_segment_comparison_plan_binds_materialized_page_cells_before_argmax():
    question = (
        "From FY21 to FY22, excluding Embedded, in which AMD reporting "
        "segment did sales proportionally increase the most?"
    )
    page = {
        "evidence_id": "AMD_2022_10K#page:48",
        "source_id": "AMD_2022_10K",
        "page_label": "48",
        "table_group_id": "segment-revenue",
        "text": (
            "Revenue by reporting segment (in millions)\n2022 2021\n"
            "Data Center 6,043 3,694\nClient 6,201 6,887\n"
            "Gaming 6,805 5,607\nEmbedded 4,552 246"
        ),
        "modality": "table",
    }
    plan = build_query_plan(
        question,
        answer_type="extractive",
        verification_domain="finance",
    )

    bound = bind_evidence_slots(plan, [page])
    result = finance_segment_comparison_answer(
        question,
        [page],
        query_plan=bound.as_dict(),
    )

    assert all(len(slot.evidence_ids) == 3 for slot in bound.evidence_slots)
    assert result is not None
    assert result.status == "ok"
    assert result.answer == "Data Center"


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
                    "Year Ended\n2022 2021\n(In millions)\n"
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


def test_segment_comparison_excludes_tables_before_revenue_section_heading():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, excluding Embedded, in which AMD reporting "
            "segment did sales proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "AMD_2022_10K#page:48",
                "source_id": "AMD_2022_10K",
                "page_label": "48",
                "modality": "table",
                "text": (
                    "Accrued liabilities (in millions)\n2022 2021\n"
                    "Data Center 1 9000\nClient 1 8000\nGaming 1 7000\n"
                    "Year Ended\n2022 2021\n(In millions)\nNet revenue:\n"
                    "Data Center 6,043 3,694\nClient 6,201 6,887\n"
                    "Gaming 6,805 5,607\nEmbedded 4,552 246\n"
                    "Total net revenue 23,601 16,434"
                ),
            }
        ],
    )

    assert result is not None
    assert result.status == "ok"
    assert result.answer == "Data Center"
    assert result.scale == "million"
    assert result.audit_status == "passed"


def test_segment_comparison_requires_local_scale_provenance():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "scale-missing",
                "text": (
                    "Revenue by reporting segment\n2022 2021\n"
                    "Data Center 6,043 3,694\nClient 6,201 6,887"
                ),
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.answer == ""
    assert result.audit_status == "failed"


def test_segment_comparison_rejects_wrong_period_matrix():
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        [
            {
                "evidence_id": "wrong-periods",
                "text": (
                    "Revenue by reporting segment (in millions)\n2023 2022\n"
                    "Data Center 7,000 6,043\nClient 6,400 6,201"
                ),
                "modality": "table",
            }
        ],
    )

    assert result is not None
    assert result.answer == ""
    assert result.audit_status == "failed"


def test_segment_comparison_rejects_mixed_scale_matrix():
    items = []
    for entity, period, value, scale in (
        ("Data Center", "2021", "3694", "million"),
        ("Data Center", "2022", "6043", "million"),
        ("Client", "2021", "6.887", "billion"),
        ("Client", "2022", "6.201", "billion"),
    ):
        items.append(
            {
                "evidence_id": f"{entity}-{period}",
                "cell_id": f"{entity}-{period}",
                "source_id": "AMD_2022_10K",
                "page_label": "48",
                "table_group_id": "segment-revenue",
                "evidence_level": "cell",
                "row_label": entity,
                "column_label": period,
                "period": period,
                "value": value,
                "unit": "USD",
                "scale": scale,
                "statement_kind": "segment_table",
                "financial_scope": "segment",
            }
        )

    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        items,
    )

    assert result is not None
    assert result.answer == ""
    assert result.audit_status == "failed"


def test_segment_comparison_rejects_matrix_without_currency_unit() -> None:
    items = []
    for entity, period, value in (
        ("Data Center", "2021", "3694"),
        ("Data Center", "2022", "6043"),
        ("Client", "2021", "6887"),
        ("Client", "2022", "6201"),
    ):
        items.append(
            {
                "evidence_id": f"{entity}-{period}",
                "cell_id": f"{entity}-{period}",
                "source_id": "AMD_2022_10K",
                "page_label": "48",
                "table_group_id": "segment-revenue",
                "evidence_level": "cell",
                "row_label": entity,
                "column_label": period,
                "period": period,
                "value": value,
                "unit": "",
                "scale": "million",
                "statement_kind": "segment_table",
                "financial_scope": "segment",
            }
        )

    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        items,
    )

    assert result is not None
    assert result.answer == ""
    assert result.audit_status == "failed"


def test_segment_comparison_does_not_merge_periods_across_tables():
    items = []
    for table, period, values in (
        ("fy21-table", "2021", (("Data Center", "3694"), ("Client", "6887"))),
        ("fy22-table", "2022", (("Data Center", "6043"), ("Client", "6201"))),
    ):
        for entity, value in values:
            items.append(
                {
                    "evidence_id": f"{table}-{entity}",
                    "cell_id": f"{table}-{entity}",
                    "source_id": "AMD_2022_10K",
                    "page_label": "48",
                    "table_group_id": table,
                    "evidence_level": "cell",
                    "row_label": entity,
                    "column_label": period,
                    "period": period,
                    "value": value,
                    "unit": "USD",
                    "scale": "million",
                    "statement_kind": "segment_table",
                    "financial_scope": "segment",
                }
            )

    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        items,
    )

    assert result is not None
    assert result.answer == ""
    assert result.audit_status == "failed"


def test_segment_comparison_rejects_identical_matrices_on_distinct_pages():
    table = (
        "Revenue by reporting segment (in millions)\n2022 2021\n"
        "Data Center 6,043 3,694\nClient 6,201 6,887"
    )
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        [
            {
                "evidence_id": f"segment-{page}",
                "source_id": "AMD_2022_10K",
                "page_label": page,
                "text": table,
                "modality": "table",
            }
            for page in ("48", "67")
        ],
    )

    assert result is not None
    assert result.answer == ""
    assert result.status == "ambiguous_matrix"


def test_segment_comparison_rejects_identical_matrices_from_distinct_tables():
    table = (
        "Revenue by reporting segment (in millions)\n2022 2021\n"
        "Data Center 6,043 3,694\nClient 6,201 6,887"
    )
    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        [
            {
                "evidence_id": f"segment-{table_id}",
                "source_id": "AMD_2022_10K",
                "page_label": "48",
                "table_group_id": table_id,
                "text": table,
                "modality": "table",
            }
            for table_id in ("segment-revenue-a", "segment-revenue-b")
        ],
    )

    assert result is not None
    assert result.answer == ""
    assert result.status == "ambiguous_matrix"


def test_segment_comparison_separates_instances_within_one_table_group() -> None:
    items = []
    for instance, offset in (("segment-a", 0), ("segment-b", 100)):
        for entity, prior, current in (
            ("Data Center", 3694, 6043),
            ("Client", 6887, 6201),
        ):
            for period, value in (("2021", prior + offset), ("2022", current + offset)):
                items.append(
                    {
                        "evidence_id": f"{instance}-{entity}-{period}",
                        "cell_id": f"{instance}-{entity}-{period}",
                        "source_id": "AMD_2022_10K",
                        "page_label": "48",
                        "table_group_id": "segment-revenue-group",
                        "table_instance_id": instance,
                        "evidence_level": "cell",
                        "row_label": entity,
                        "column_label": period,
                        "period": period,
                        "value": str(value),
                        "unit": "USD",
                        "scale": "million",
                        "statement_kind": "segment_table",
                        "financial_scope": "segment",
                    }
                )

    result = finance_segment_comparison_answer(
        (
            "From FY21 to FY22, in which reporting segment did sales "
            "proportionally increase the most?"
        ),
        items,
    )

    assert result is not None
    assert result.answer == ""
    assert result.status == "ambiguous_matrix"


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
