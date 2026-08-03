from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_scale import source_scale_evidence
from ktem.docqa.financial_table import parse_financial_table_cells
from ktem.docqa.query_plan_schema import EvidenceSlot
from ktem.docqa.query_planning import build_query_plan, score_evidence_for_slot
from ktem.docqa.required_slot_selection import required_slot_candidate_limit
from ktem.docqa.retrieval_rounds import retrieve_with_rounds


def test_fixed_asset_turnover_plan_has_revenue_and_two_ppe_operands():
    plan = build_query_plan(
        (
            "What is the FY2019 fixed asset turnover ratio? The ratio is "
            "FY2019 revenue divided by average PP&E between FY2018 and FY2019."
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [(slot.metric, slot.period) for slot in plan.evidence_slots] == [
        ("net sales", "2019"),
        ("net property plant and equipment", "2018"),
        ("net property plant and equipment", "2019"),
    ]


def test_fixed_asset_turnover_expression_uses_average_ppe():
    plan = build_query_plan(
        (
            "What is the FY2019 fixed asset turnover ratio? The ratio is "
            "FY2019 revenue divided by average PP&E between FY2018 and FY2019."
        ),
        answer_type="numeric",
        verification_domain="finance",
    )
    formula = plan.constraints["finance_formula"]

    assert formula["formula_id"] == "fixed_asset_turnover"
    assert formula["formula_match_rule"] == "alias:fixed_asset_turnover"
    assert formula["formula_confidence"] == 1.0
    assert formula["target_period"] == "2019"
    assert formula["previous_period"] == "2018"
    assert formula["expression_ast"] == {
        "operator": "divide",
        "inputs": [
            {"ref": "operand:net_sales:2019"},
            {
                "operator": "average",
                "inputs": [
                    {"ref": "operand:net_property_plant_and_equipment:2018"},
                    {"ref": "operand:net_property_plant_and_equipment:2019"},
                ],
            },
        ],
    }


def test_formula_registry_overrides_generic_planner_payload():
    plan = build_query_plan(
        (
            "What is FY2019 fixed asset turnover using FY2019 revenue and "
            "average net PP&E for FY2018 and FY2019?"
        ),
        answer_type="numeric",
        verification_domain="finance",
        planner_payload={
            "answer_type": "numeric",
            "question_type": "multi_period_numeric",
            "evidence_slots": [
                {
                    "slot_id": "operand:revenue:2019",
                    "role": "operand",
                    "metric": "revenue",
                    "period": "2019",
                },
                {
                    "slot_id": "operand:revenue:2018",
                    "role": "operand",
                    "metric": "revenue",
                    "period": "2018",
                },
            ],
        },
    )

    assert plan.constraints["finance_formula"]["formula_id"] == ("fixed_asset_turnover")
    assert [slot.metric for slot in plan.evidence_slots] == [
        "net sales",
        "net property plant and equipment",
        "net property plant and equipment",
    ]


def test_unknown_formula_does_not_fall_back_to_wrong_revenue_plan():
    plan = build_query_plan(
        "What was the revenue productivity turnover from FY2018 to FY2019?",
        answer_type="numeric",
        verification_domain="finance",
    )

    assert plan.evidence_slots == ()
    assert plan.constraints["finance_formula_status"] == "unsupported"


def test_year_header_cannot_be_numeric_operand():
    slot = EvidenceSlot(
        slot_id="operand:capital_expenditure:2018",
        role="operand",
        metric="capital expenditure",
        period="2018",
        required_for_execution=True,
    )
    parent = {
        "evidence_id": "cash-flow-table",
        "source_id": "3m",
        "page_label": "60",
        "table_id": "cash-flow-table",
        "modality": "table",
        "text": "2018 2017\nCapital expenditure (1,577) (1,373)",
    }
    header = {
        **parent,
        "evidence_id": "year-header",
        "cell_id": "year-header",
        "evidence_level": "cell",
        "cell_role": "header",
        "row_label": "Year",
        "column_label": "2018",
        "period": "2018",
        "value": "2018",
    }

    assert score_evidence_for_slot(slot, parent) == 0.0
    assert score_evidence_for_slot(slot, header) == 0.0


def test_capex_2018_binds_1577_not_2018():
    cells = parse_financial_table_cells(
        {
            "evidence_id": "cash-flow-page-60",
            "source_id": "3m",
            "page_label": "60",
            "table_id": "cash-flow-page-60",
            "modality": "table",
            "text": (
                "Consolidated Statement of Cash Flows\n"
                "(Millions)\n"
                "Years ended December 31\n"
                "2018\n"
                "2017\n"
                "2016\n"
                "Purchases of property, plant and equipment (PP&E)\n"
                "$\n"
                "(1,577)\n"
                "$\n"
                "(1,373)\n"
                "$\n"
                "(1,420)\n"
            ),
        }
    )

    capex_2018 = next(
        cell
        for cell in cells
        if cell.period == "2018" and "property" in cell.row_label.lower()
    )
    assert capex_2018.value == -1577
    assert capex_2018.cell_role == "data"
    assert all(cell.value != 2018 for cell in cells)


def test_glued_month_year_header_materializes_operating_income_cells():
    cells = parse_financial_table_cells(
        {
            "evidence_id": "adobe-income",
            "source_id": "adobe",
            "page_label": "62",
            "table_id": "adobe-income",
            "modality": "table",
            "text": (
                "CONSOLIDA TED ST ATEMENTS OF INCOME\n"
                "(In thousands)\n"
                "Years Ended\n"
                "December 2,\n"
                "2016November 27,\n"
                "2015November 28,\n"
                "2014\n"
                "Operating income 1,493,602 903,095 412,685"
            ),
        }
    )

    assert [
        (cell.period, cell.value)
        for cell in cells
        if cell.row_label == "Operating income"
    ] == [
        ("2016", 1493602),
        ("2015", 903095),
        ("2014", 412685),
    ]


def test_amount_and_percentage_subcolumns_bind_amount_not_100_percent():
    cells = parse_financial_table_cells(
        {
            "evidence_id": "operations-table",
            "source_id": "activision",
            "page_label": "37",
            "table_id": "operations-table",
            "modality": "table",
            "text": (
                "Consolidated Statements of Operations Data (in millions)\n"
                "2019 2018\n"
                "Total net revenues 6,489 100 7,500 100"
            ),
        }
    )

    assert [
        (cell.period, cell.value)
        for cell in cells
        if cell.row_label == "Total net revenues"
    ] == [("2019", 6489), ("2018", 7500)]


def test_trailing_row_labels_materialize_cells_from_pdf_reading_order() -> None:
    cells = parse_financial_table_cells(
        {
            "evidence_id": "nike-income",
            "source_id": "nike",
            "page_label": "46",
            "table_id": "nike-income",
            "modality": "table",
            "text": (
                "NIKE, Inc. Consolidated Statements of Income\n"
                "Year Ended May 31, (In millions)\n"
                "2018 2017 2016 Revenues\n"
                "$36,397 $34,350 $32,376 Cost of sales\n"
                "20,441 19,038 17,405 Gross profit\n"
                "15,956 15,312 14,971"
            ),
        }
    )

    assert [
        (cell.row_label, cell.period, cell.value)
        for cell in cells
        if cell.row_label in {"Revenues", "Cost of sales"}
    ] == [
        ("Revenues", "2018", 36397),
        ("Revenues", "2017", 34350),
        ("Revenues", "2016", 32376),
        ("Cost of sales", "2018", 20441),
        ("Cost of sales", "2017", 19038),
        ("Cost of sales", "2016", 17405),
    ]


def test_scale_dimension_binds_to_same_table_group():
    operand = {
        "evidence_id": "capex-cell",
        "source_id": "report",
        "page_label": "60",
        "cell_id": "capex-cell",
        "evidence_level": "cell",
        "table_instance_id": "cash-flow",
        "table_group_id": "cash-flow",
        "value": "-1577",
    }
    same_table_header = {
        "evidence_id": "cash-flow-caption",
        "source_id": "report",
        "page_label": "60",
        "evidence_level": "span",
        "span_id": "cash-flow-caption",
        "table_instance_id": "cash-flow",
        "table_group_id": "cash-flow",
        "text": "Consolidated cash flows (in millions)",
    }
    unrelated_header = {
        "evidence_id": "other-caption",
        "source_id": "report",
        "page_label": "8",
        "evidence_level": "span",
        "span_id": "other-caption",
        "table_instance_id": "other-table",
        "table_group_id": "other-table",
        "text": "Amounts in billions",
    }

    assert source_scale_evidence(
        operand,
        [operand, unrelated_header, same_table_header],
    ) == ("million", "cash-flow-caption")


def test_parent_table_cannot_fill_execution_slot():
    slot = EvidenceSlot(
        slot_id="operand:operating_income:2015",
        role="operand",
        metric="operating income",
        period="2015",
        required_for_execution=True,
    )
    parent = {
        "evidence_id": "income-table",
        "source_id": "adobe",
        "page_label": "52",
        "table_id": "income-table",
        "modality": "table",
        "text": "2016 2015\nOperating income 900 544",
    }

    assert score_evidence_for_slot(slot, parent) == 0.0


def test_parent_table_materializes_distinct_period_cells():
    request = DocQARequest(
        prompt=(
            "What was the percentage change in operating income from "
            "FY2015 to FY2016?"
        ),
        task_type="numeric",
        verification_domain="finance",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "income-table",
                    "source_id": "adobe",
                    "page_label": "52",
                    "table_id": "income-table",
                    "table_instance_id": "income-table",
                    "table_group_id": "income-statement",
                    "modality": "table",
                    "text": (
                        "Consolidated Statements of Income (in millions)\n"
                        "2016 2015\nOperating income 900 544"
                    ),
                }
            ]
        },
    )

    cells = [
        item
        for item in bundle.metadata["canonical_candidate_evidence"]
        if item.get("evidence_level") == "cell"
    ]
    assert {(item["period"], item["value"]) for item in cells} == {
        ("2016", "900"),
        ("2015", "544"),
    }
    assert len({item["canonical_id"] for item in cells}) == 2


def test_materialized_cells_execute_multi_period_percentage_change():
    question = (
        "What was the year-over-year change in operating income from "
        "FY2015 to FY2016 in percents?"
    )
    request = DocQARequest(
        prompt=question,
        task_type="numeric",
        verification_domain="finance",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "adobe-income",
                    "source_id": "adobe",
                    "page_label": "62",
                    "table_id": "adobe-income",
                    "modality": "table",
                    "text": (
                        "Consolidated Statements of Income (in thousands)\n"
                        "2016 2015\nOperating income 1,493,602 903,095"
                    ),
                }
            ]
        },
    )

    answer = finance_numeric_answer(
        question,
        bundle.items,
        query_plan=bundle.metadata["query_plan"],
    )

    assert answer is not None
    assert answer.answer == "65.4%"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["status"] == "ok"


def test_execution_cell_materialization_is_slot_scoped_and_cached():
    request = DocQARequest(
        prompt=(
            "What was the percentage change in operating income from "
            "FY2015 to FY2016?"
        ),
        task_type="numeric",
        verification_domain="finance",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "income-table",
                    "source_id": "adobe",
                    "page_label": "62",
                    "table_id": "income-table",
                    "table_instance_id": "income-table",
                    "modality": "table",
                    "text": (
                        "Consolidated Statements of Income (in thousands)\n"
                        "2016 2015\n"
                        "Operating income 1,493,602 903,095\n"
                        "Net revenue 4,796,000 4,100,000\n"
                        "Cost of revenue 500,000 450,000"
                    ),
                }
            ]
        },
    )

    trace = bundle.metadata["materialization_trace"]
    cells = [
        item
        for item in bundle.metadata["canonical_candidate_evidence"]
        if item.get("evidence_level") == "cell"
    ]
    assert {(item["row_label"], item["period"]) for item in cells} == {
        ("Operating income", "2015"),
        ("Operating income", "2016"),
    }
    assert trace["materialized_table_count"] == 1
    assert trace["materialization_cache_hit_rate"] > 0
    assert trace["candidate_count_after_materialization"] == (
        trace["candidate_count_before_materialization"] + 2
    )


def test_period_slots_cannot_share_parent_identity():
    request = DocQARequest(
        prompt=(
            "What was the percentage change in operating income from "
            "FY2015 to FY2016?"
        ),
        task_type="numeric",
        verification_domain="finance",
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "income-table",
                    "source_id": "adobe",
                    "page_label": "52",
                    "table_id": "income-table",
                    "modality": "table",
                    "text": (
                        "Consolidated Statements of Income\n"
                        "2016 2015\nOperating income 900 544"
                    ),
                }
            ]
        },
    )
    slots = bundle.metadata["query_plan"]["evidence_slots"]

    assert all(slot["status"] == "filled" for slot in slots)
    assert len({slot["evidence_ids"][0] for slot in slots}) == 2
    assert all(
        evidence_id.startswith("cell:")
        for slot in slots
        for evidence_id in slot["evidence_ids"]
    )


def test_six_operand_plan_preserves_every_metric_period_pair():
    plan = build_query_plan(
        ("What is the FY2017 - FY2019 3 year average of capex as a % " "of revenue?"),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert {(slot.metric, slot.period) for slot in plan.evidence_slots} == {
        ("capital expenditure", "2017"),
        ("capital expenditure", "2018"),
        ("capital expenditure", "2019"),
        ("net sales", "2017"),
        ("net sales", "2018"),
        ("net sales", "2019"),
    }
    assert required_slot_candidate_limit(plan, base_limit=4) >= 12


def test_required_slot_retrieval_runs_one_query_per_missing_slot():
    calls: list[tuple[int, str, str]] = []

    def retrieve(request, _decision):
        calls.append(
            (
                request.retrieval_round_id,
                request.retrieval_slot_id,
                request.retrieval_query,
            )
        )
        metric, period = request.retrieval_query.rsplit(" ", 1)
        if metric.startswith("capital expenditure"):
            metric = "capital expenditure"
        statement_kind = (
            "cash_flow_statement"
            if metric == "capital expenditure"
            else "income_statement"
        )
        return {
            "evidence": [
                {
                    "evidence_id": f"{metric}:{period}",
                    "source_id": "report",
                    "page_label": period,
                    "element_id": f"{metric}-table",
                    "table_id": f"{metric}-table",
                    "cell_id": f"{metric}:{period}",
                    "evidence_level": "cell",
                    "cell_role": "data",
                    "row_label": metric,
                    "column_label": period,
                    "period": period,
                    "value": "10",
                    "statement_kind": statement_kind,
                    "financial_scope": "consolidated",
                    "modality": "table",
                    "text": f"{metric} {period} 10",
                }
            ]
        }

    request = DocQARequest(
        prompt=(
            "What is the FY2017 - FY2019 3 year average of capex as a % " "of revenue?"
        ),
        task_type="numeric",
        verification_domain="finance",
    )
    retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=lambda *_args, **_kwargs: SimpleNamespace(
            status="good",
            retry=False,
        ),
        retry_poor=False,
    )

    assert len(calls) == 6
    assert all(round_id == 1 for round_id, _slot_id, _query in calls)
    assert len({slot_id for _round_id, slot_id, _query in calls}) == 6
    assert all(query.strip() for _round_id, _slot_id, query in calls)
