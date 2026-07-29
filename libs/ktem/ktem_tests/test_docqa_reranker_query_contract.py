from __future__ import annotations

from decimal import Decimal

from ktem.docqa.calculation_evidence_identity import materialize_financial_cell
from ktem.docqa.evidence_ranking_trace import materialize_reranked_candidates
from ktem.docqa.financial_table import FinancialTableCell
from ktem.docqa.retrieval_rounds import (
    _merge_retrieval_metadata,
    _with_retrieval_lineage,
)


def _trace(query_id: str, slot_id: str, identity: str, *, output_count: int = 1):
    return {
        "configured": True,
        "loaded": True,
        "executed": True,
        "backend": "tei",
        "model": "bge",
        "query_id": query_id,
        "slot_id": slot_id,
        "round_id": 1,
        "input_count": 1,
        "output_count": output_count,
        "input_identities": [identity],
        "output_identities": [identity],
        "score_field": "reranker_score",
    }


def test_multiple_slot_reranker_traces_are_not_overwritten():
    merged = _merge_retrieval_metadata(
        {"reranker_execution_traces": [_trace("q:left", "left", "raw:a")]},
        {"reranker_execution_traces": [_trace("q:right", "right", "raw:b")]},
    )

    assert [trace["query_id"] for trace in merged["reranker_execution_traces"]] == [
        "q:left",
        "q:right",
    ]


def test_reranker_query_trace_preserves_query_slot_round():
    metadata = _with_retrieval_lineage(
        {
            "reranker_execution_trace": _trace("", "", "raw:a"),
            "evidence": [{"source_id": "paper", "span_id": "a", "text": "A"}],
        },
        round_id=2,
        query_id="round2:operand",
        slot_id="operand:revenue",
    )

    trace = metadata["reranker_execution_traces"][0]
    assert (trace["query_id"], trace["slot_id"], trace["round_id"]) == (
        "round2:operand",
        "operand:revenue",
        2,
    )


def test_duplicate_identity_merges_observations_not_lineage():
    candidates = [
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:a",
            "reranker_score": 0.9,
        },
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:b",
            "reranker_score": 0.8,
        },
    ]

    output, ranking = materialize_reranked_candidates(
        candidates,
        {
            "reranker_execution_traces": [
                _trace("q:left", "left", "raw:a"),
                _trace("q:right", "right", "raw:b"),
            ]
        },
        limit=30,
    )

    assert len(output or []) == 1
    assert len((output or [])[0]["reranker_observations"]) == 2
    assert ranking["query_execution_count"] == 2


def test_backend_output_total_can_exceed_unique_identity_count():
    candidates = [
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:a",
            "reranker_score": 0.9,
        },
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:b",
            "reranker_score": 0.8,
        },
    ]

    _output, ranking = materialize_reranked_candidates(
        candidates,
        {
            "reranker_execution_traces": [
                _trace("q:left", "left", "raw:a"),
                _trace("q:right", "right", "raw:b"),
            ]
        },
        limit=30,
    )

    assert ranking["backend_output_total"] == 2
    assert ranking["unique_output_identity_count"] == 1


def test_full_artifact_count_matches_unique_reranked_identity_count():
    candidates = [
        {
            "source_id": "paper",
            "span_id": "a",
            "reranker_input_identity": "raw:a",
            "reranker_score": 0.9,
        },
        {
            "source_id": "paper",
            "span_id": "b",
            "reranker_input_identity": "raw:b",
            "reranker_score": 0.8,
        },
    ]

    output, ranking = materialize_reranked_candidates(
        candidates,
        {
            "reranker_execution_traces": [
                _trace("q:left", "left", "raw:a"),
                _trace("q:right", "right", "raw:b"),
            ]
        },
        limit=30,
    )

    assert ranking["reranker_artifact_record_count"] == len(output or [])
    assert ranking["unique_output_identity_count"] == len(output or [])


def test_selection_retained_count_is_not_reported_as_reranker_output():
    _output, ranking = materialize_reranked_candidates(
        [
            {
                "source_id": "paper",
                "span_id": "a",
                "reranker_input_identity": "raw:a",
                "reranker_score": 0.9,
            }
        ],
        {"reranker_execution_traces": [_trace("q", "slot", "raw:a")]},
        limit=30,
    )

    assert ranking["selection_retained_reranked_count"] is None
    assert ranking["backend_output_total"] == 1


def test_configured_loaded_reranker_without_execution_fails_gate():
    output, ranking = materialize_reranked_candidates(
        [{"source_id": "paper", "span_id": "a", "text": "A"}],
        {
            "reranker_execution_traces": [
                {
                    "configured": True,
                    "loaded": True,
                    "executed": False,
                    "query_id": "q",
                    "slot_id": "slot",
                    "round_id": 1,
                }
            ]
        },
        limit=30,
    )

    assert output is None
    assert ranking["configured"] is True
    assert ranking["loaded"] is True
    assert ranking["executed"] is False


def test_partial_reranker_pool_materializes_real_stage():
    output, _ranking = materialize_reranked_candidates(
        [
            {
                "source_id": "paper",
                "span_id": "a",
                "reranker_input_identity": "raw:a",
                "reranker_score": 0.9,
            },
            {"source_id": "paper", "span_id": "protected", "text": "protected"},
        ],
        {"reranker_execution_traces": [_trace("q", "slot", "raw:a")]},
        limit=30,
    )

    assert [item["span_id"] for item in output or []] == ["a"]


def test_materialized_cell_does_not_inherit_parent_reranker_observation():
    parent = {
        "source_id": "report",
        "evidence_id": "table",
        "table_id": "table",
        "page_label": "1",
        "text": "2022\nRevenue 100",
        "reranker_score": 0.9,
        "reranker_input_identity": "raw:table",
        "metadata": {
            "reranker_score": 0.9,
            "reranker_execution_trace": {"executed": True},
        },
    }
    cell = FinancialTableCell(
        cell_id="revenue-2022",
        evidence_id="revenue-2022",
        canonical_id="",
        source_id="report",
        page_label="1",
        table_id="table",
        table_instance_id="table",
        table_group_id="table",
        block_id="block",
        row_index=1,
        column_index=1,
        row_label="Revenue",
        column_label="2022",
        period="2022",
        value=Decimal("100"),
    )

    materialized = materialize_financial_cell(parent, cell)

    assert "reranker_score" not in materialized
    assert "reranker_input_identity" not in materialized
    assert "reranker_score" not in materialized["metadata"]
