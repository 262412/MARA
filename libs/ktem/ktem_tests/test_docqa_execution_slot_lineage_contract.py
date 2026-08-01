from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.calculation_evidence_identity import materialize_financial_cell
from ktem.docqa.evidence import _materialize_execution_cells
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_scale import compatible_dimension_scope
from ktem.docqa.financial_table import parse_financial_table_cells
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan
from ktem.docqa.required_slot_selection import required_slot_shortlist

QUESTION = (
    "What was FY2021 net working capital, defined as current assets less "
    "current liabilities?"
)


def _cell(
    evidence_id: str,
    row_label: str,
    value: str,
    *,
    period: str = "2021",
    continuation_id: str = "",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "canonical_id": f"cell:report:{evidence_id}",
        "source_id": "report",
        "page_label": "12",
        "table_id": "balance-sheet",
        "table_instance_id": "balance-sheet-block-1",
        "table_group_id": "balance-sheet",
        "materialization_source_id": "balance-sheet-parent",
        "continuation_id": continuation_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "cell_id": evidence_id,
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "value": value,
        "statement_kind": "balance_sheet",
        "financial_scope": "consolidated",
        "text": f"{row_label} {period} {value}",
        "metadata": {
            "reranker_observations": [
                {
                    "query_id": f"query:{evidence_id}",
                    "slot_id": f"slot:{evidence_id}",
                    "score": 0.9,
                }
            ]
        },
    }


def _parent() -> dict[str, Any]:
    return {
        "evidence_id": "balance-sheet-parent",
        "canonical_id": "element:report:balance-sheet-parent",
        "source_id": "report",
        "page_label": "12",
        "element_id": "balance-sheet-parent",
        "element_type": "table",
        "modality": "table",
        "table_id": "balance-sheet",
        "table_instance_id": "balance-sheet-block-1",
        "table_group_id": "balance-sheet",
        "statement_kind": "balance_sheet",
        "financial_scope": "consolidated",
        "text": (
            "CONSOLIDATED BALANCE SHEETS\n"
            "2021 2020\n"
            "Current assets 20,991 19,378\n"
            "Current liabilities 15,173 15,911"
        ),
    }


def _plan():
    return build_query_plan(
        QUESTION,
        answer_type="numeric",
        verification_domain="finance",
    )


def test_each_execution_slot_has_independent_candidate_quota() -> None:
    plan = _plan()
    assets = _cell("assets", "Current assets", "20991")
    liabilities = _cell("liabilities", "Current liabilities", "15173")
    assets["metadata"]["reranking_score"] = 0.99
    liabilities["metadata"]["reranking_score"] = 0.98
    distractors = [
        _cell(f"assets-{index}", "Current assets", str(10000 + index))
        for index in range(8)
    ]

    candidates, _restored = required_slot_shortlist(
        [*distractors, _parent(), assets, liabilities],
        plan,
        candidate_limit=6,
    )

    selected_ids = {item["evidence_id"] for item in candidates}
    assert {"assets", "liabilities"} <= selected_ids
    assert "balance-sheet-parent" in selected_ids


def test_joint_selection_preserves_all_required_operands() -> None:
    plan = _plan()
    assets = _cell("assets", "Current assets", "20991")
    liabilities = _cell("liabilities", "Current liabilities", "15173")

    selected, trace, bound = select_evidence_for_plan(
        QUESTION,
        [_parent(), assets, liabilities],
        plan,
    )

    assert {item["evidence_id"] for item in selected} >= {"assets", "liabilities"}
    assert "balance-sheet-parent" in {item["evidence_id"] for item in selected}
    assert all(
        slot.status == "filled"
        for slot in bound.evidence_slots
        if slot.required_for_execution and slot.role == "operand"
    )
    assert all(
        binding["selected_cell"]
        for binding in trace["execution_slot_lineage"]
        if binding["slot_id"].startswith("operand:")
    )
    for binding in trace["required_slot_bindings"]:
        assert binding["candidate_selection_reasons"]
        assert "candidate_drop_reasons" in binding


def test_correct_cell_survives_global_reranking() -> None:
    plan = _plan()
    assets = _cell("assets", "Current assets", "20991")
    liabilities = _cell("liabilities", "Current liabilities", "15173")
    for index, item in enumerate((assets, liabilities)):
        item["metadata"]["reranking_score"] = 0.01 + index * 0.001
    noise = [
        {
            **_cell(f"noise-{index}", "Current assets", str(index + 1)),
            "metadata": {"reranking_score": 1.0 - index * 0.01},
        }
        for index in range(12)
    ]

    selected, _trace, _bound = select_evidence_for_plan(
        QUESTION,
        [*noise, assets, liabilities],
        plan,
    )

    assert {item["evidence_id"] for item in selected} >= {"assets", "liabilities"}


def test_parent_table_materializes_only_relevant_rows_and_periods() -> None:
    request = SimpleNamespace(
        prompt=QUESTION,
        task_type="numeric",
        verification_domain="finance",
        query_plan=_plan(),
    )
    metadata: dict[str, Any] = {}

    materialized = _materialize_execution_cells(request, [_parent()], metadata)
    cells = [item for item in materialized if item.get("evidence_level") == "cell"]

    assert {(item["row_label"], item["period"]) for item in cells} == {
        ("Current assets", "2021"),
        ("Current liabilities", "2021"),
    }
    assert metadata["materialization_trace"]["materialized_cells_by_required_slot"]


def test_continuation_table_cells_keep_parent_lineage() -> None:
    parent = {
        **_parent(),
        "continuation_id": "balance-sheet-continuation",
        "neighbor_element_ids": ["balance-sheet-block-2"],
    }
    cell = next(
        item
        for item in parse_financial_table_cells(parent)
        if item.row_label == "Current assets" and item.period == "2021"
    )

    materialized = materialize_financial_cell(parent, cell)

    assert materialized["materialization_source_id"] == parent["evidence_id"]
    assert materialized["continuation_id"] == "balance-sheet-continuation"
    assert materialized["table_group_id"] == "balance-sheet"


def test_dimension_evidence_is_not_a_numeric_operand() -> None:
    dimension = {
        "evidence_id": "scale",
        "source_id": "report",
        "page_label": "12",
        "evidence_level": "element",
        "scale": "million",
        "text": "USD in millions",
    }
    bound = bind_evidence_slots(_plan(), [dimension])

    assert all(
        slot.status == "missing"
        for slot in bound.evidence_slots
        if slot.role == "operand" and slot.required_for_execution
    )


def test_selected_slot_coverage_requires_executable_cell() -> None:
    parent_only = bind_evidence_slots(_plan(), [_parent()])
    with_cells = bind_evidence_slots(
        _plan(),
        [
            _cell("assets", "Current assets", "20991"),
            _cell("liabilities", "Current liabilities", "15173"),
        ],
    )

    assert any(
        slot.status == "missing"
        for slot in parent_only.evidence_slots
        if slot.role == "operand" and slot.required_for_execution
    )
    assert all(
        slot.status == "filled"
        for slot in with_cells.evidence_slots
        if slot.role == "operand" and slot.required_for_execution
    )


def test_execution_success_requires_every_required_operand() -> None:
    incomplete = finance_numeric_answer(
        QUESTION, [_cell("assets", "Current assets", "20991")]
    )

    assert incomplete is None or incomplete.calculation_execution["status"] != "ok"


def test_correct_execution_reaches_final_answer() -> None:
    answer = finance_numeric_answer(
        QUESTION,
        [
            _cell("assets", "Current assets", "20991"),
            _cell("liabilities", "Current liabilities", "15173"),
        ],
    )

    assert answer is not None
    assert answer.calculation_execution["status"] == "ok"
    assert answer.answer == "$5,818.0"


def test_inventory_turnover_query_plan_executes_bound_atomic_cells() -> None:
    question = (
        "What is FY2019 inventory turnover, defined as FY2019 COGS divided "
        "by average inventory between FY2018 and FY2019?"
    )
    evidence = [
        {
            **_cell("cogs", "Cost of products sold", "16830", period="2019"),
            "statement_kind": "income_statement",
        },
        _cell("inventory-2018", "Inventories", "2667", period="2018"),
        _cell("inventory-2019", "Inventories", "2721", period="2019"),
    ]

    answer = finance_numeric_answer(
        question,
        evidence,
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ).as_dict(),
    )

    assert answer is not None
    assert answer.question_type == "inventory_turnover_average"
    assert answer.calculation_execution["status"] == "ok"
    assert answer.answer == "6.25"


def test_dimension_slot_binds_only_to_selected_operand_scope() -> None:
    question = "What was FY2021 capital expenditure in USD billions?"
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    operand = {
        **_cell("capex", "Capital expenditure", "4625"),
        "page_label": "20",
        "table_instance_id": "cash-flow-table",
        "table_group_id": "cash-flow",
        "statement_kind": "cash_flow_statement",
    }
    unrelated_dimension = {
        "evidence_id": "balance-scale",
        "source_id": "report",
        "page_label": "10",
        "table_instance_id": "balance-sheet-table",
        "table_group_id": "balance-sheet",
        "evidence_level": "element",
        "scale": "million",
        "text": "Consolidated balance sheets (in millions)",
    }
    relevant_dimension = {
        "evidence_id": "cash-flow-scale",
        "source_id": "report",
        "page_label": "20",
        "table_instance_id": "cash-flow-table",
        "table_group_id": "cash-flow",
        "evidence_level": "element",
        "scale": "million",
        "text": "Consolidated cash flows (in millions)",
    }

    bound = bind_evidence_slots(
        plan,
        [unrelated_dimension, relevant_dimension, operand],
    )
    [dimension_slot] = [
        slot for slot in bound.evidence_slots if slot.role == "dimension"
    ]

    assert dimension_slot.status == "filled"
    assert dimension_slot.evidence_ids == (identity_of(relevant_dimension).key,)


def test_trailing_row_label_revenue_materializes_for_net_sales_slot() -> None:
    question = (
        "What is the three year average cost of goods sold as a percentage "
        "of revenue from FY2016 to FY2018?"
    )
    request = SimpleNamespace(
        prompt=question,
        task_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
    )
    table = {
        "evidence_id": "income-statement",
        "source_id": "report",
        "page_label": "46",
        "element_type": "table",
        "modality": "table",
        "table_instance_id": "income-table",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": (
            "Year Ended May 31, (In millions)\n"
            "2018 2017 2016 Revenues\n"
            "$36,397 $34,350 $32,376 Cost of sales\n"
            "20,441 19,038 17,405 Gross profit\n"
            "15,956 15,312 14,971"
        ),
    }

    materialized = _materialize_execution_cells(request, [table], {})
    revenue_cells = [
        item for item in materialized if item.get("row_label") == "Revenues"
    ]

    assert {item["period"] for item in revenue_cells} == {"2016", "2017", "2018"}


def test_financial_numeric_span_is_an_executable_operand() -> None:
    question = (
        "As of May 26, 2023, what is the total amount available under the "
        "revolving credit agreements?"
    )
    span = {
        "evidence_id": "span:report:2:credit-capacity",
        "element_id": "credit-capacity",
        "source_id": "report",
        "page_label": "2",
        "evidence_level": "span",
        "row_label": "revolving credit capacity",
        "period": "2023",
        "column_label": "2023",
        "value": "4200000000",
        "currency": "USD",
        "text": (
            "On May 26, 2023, the company entered into a $4,200,000,000 "
            "unsecured revolving credit agreement."
        ),
    }

    bound = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        [span],
    )

    [operand] = [slot for slot in bound.evidence_slots if slot.role == "operand"]
    assert operand.status == "filled"
    assert operand.evidence_ids == (identity_of(span).key,)


def test_materialized_cell_does_not_inherit_parent_runtime_identity() -> None:
    parent = {
        **_parent(),
        "runtime_identity": "element:report:balance-sheet-parent",
        "evaluation_identity": "element:fixture:balance-sheet-parent",
        "metadata": {
            "runtime_identity": "element:report:balance-sheet-parent",
            "evaluation_identity": "element:fixture:balance-sheet-parent",
        },
    }
    cell = next(
        item
        for item in parse_financial_table_cells(parent)
        if item.row_label == "Current assets" and item.period == "2021"
    )

    materialized = materialize_financial_cell(parent, cell)

    assert "runtime_identity" not in materialized
    assert "evaluation_identity" not in materialized
    assert "runtime_identity" not in materialized["metadata"]
    assert "evaluation_identity" not in materialized["metadata"]
    assert "element:report:balance-sheet-parent" not in exact_evidence_aliases(
        materialized
    )


def test_revolving_credit_execution_deduplicates_page_and_atomic_spans() -> None:
    question = (
        "As of May 26, 2023, what is the total amount the company may borrow "
        "under its unsecured revolving credit agreements?"
    )
    clauses = [
        (
            "The 2023 364 Day Credit Agreement enables the company to borrow "
            "up to $4,200,000,000."
        ),
        (
            "The 2023 Five Year Credit Agreement enables the company to "
            "borrow up to $4,200,000,000."
        ),
    ]
    page = {
        "evidence_id": "credit-page",
        "source_id": "report",
        "page_label": "2",
        "evidence_level": "page",
        "text": " ".join(clauses),
    }
    spans = [
        {
            "evidence_id": f"span:report:2:capacity-{index}",
            "element_id": f"capacity-{index}",
            "source_id": "report",
            "page_label": "2",
            "evidence_level": "span",
            "row_label": "revolving credit capacity",
            "period": "2023",
            "column_label": "2023",
            "value": "4200000000",
            "currency": "USD",
            "text": clause,
        }
        for index, clause in enumerate(clauses, start=1)
    ]

    answer = finance_numeric_answer(question, [page, *spans])

    assert answer is not None
    assert answer.answer == "$8,400,000,000"
    assert answer.calculation_execution["status"] == "ok"
    assert all(
        operand.get("evidence_identity", "").startswith("span:")
        for operand in answer.calculation_plan["operands"]
    )
    assert (
        len(
            {
                operand["evidence_identity"]
                for operand in answer.calculation_plan["operands"]
            }
        )
        == 2
    )


def test_materialization_parent_is_valid_dimension_scope_without_table_metadata() -> None:
    parent = {
        "evidence_id": "page-table-parent",
        "source_id": "report",
        "page_label": "12",
        "text": "Balance sheet (in millions)",
    }
    cell = {
        "evidence_id": "cell-1",
        "source_id": "report",
        "page_label": "12",
        "table_instance_id": "parsed-table",
        "materialization_source_id": "page-table-parent",
        "evidence_level": "cell",
        "value": "100",
        "text": "Current assets 2021 100 million",
    }

    assert compatible_dimension_scope(cell, parent) is True
