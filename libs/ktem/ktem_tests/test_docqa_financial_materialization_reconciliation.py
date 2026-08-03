from ktem.docqa.calculation_evidence_identity import calculation_evidence_lookup
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def test_parent_table_replaces_stale_materialized_component_scope():
    parent_id = "element:report:111:table-income"
    stale_component = {
        "evidence_id": (
            "source:report#page:111#table-instance:table-income#block:income"
            "#row:2#column:1"
        ),
        "source_id": "report",
        "page_label": "111",
        "table_id": "table-income",
        "table_instance_id": "table-income",
        "block_id": "income",
        "materialization_source_id": parent_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_index": 2,
        "column_index": 1,
        "row_label": "Cost of products sold",
        "column_label": "2019",
        "period": "2019",
        "value": "6251",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": "Cost of products sold 2019 6251 million consolidated",
    }
    parent = {
        "evidence_id": parent_id,
        "element_id": "table-income",
        "source_id": "report",
        "page_label": "111",
        "table_id": "table-income",
        "table_instance_id": "table-income",
        "block_id": "income",
        "text": (
            "Condensed Consolidating Statements of Income\n"
            "For the Year Ended December 28, 2019\n(in millions)\n"
            "Parent Guarantor Subsidiary Issuer Non-Guarantor Subsidiaries "
            "Eliminations Consolidated\n"
            "Cost of products sold — 11,042 6,251 (463) 16,830"
        ),
    }
    question = (
        "What is FY2019 inventory turnover, defined as FY2019 COGS divided by "
        "average FY2018 and FY2019 inventory?"
    )

    bound = bind_evidence_slots(
        build_query_plan(
            question, answer_type="numeric", verification_domain="finance"
        ),
        [stale_component, parent],
    )
    cogs = next(
        slot for slot in bound.evidence_slots if slot.metric == "cost of goods sold"
    )
    lookup = calculation_evidence_lookup([stale_component, parent])
    selected = lookup[cogs.evidence_ids[0]]

    assert selected["value"] == "16830"
    assert selected["financial_scope"] == "consolidated"
    assert selected["metadata"]["column_header_path"][0] == "Consolidated"
