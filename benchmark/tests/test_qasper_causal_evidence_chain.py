from __future__ import annotations

from benchmark.qasper_causal_evidence_chain import (
    qasper_causal_evidence_chain,
    qasper_causal_evidence_chain_prefix_complete,
)
from benchmark.tests.qasper_causal_evidence_chain_fixtures import causal_row as _row


def test_zero_plan_trace_is_complete_and_names_the_decisive_stage() -> None:
    chain = qasper_causal_evidence_chain(
        _row(ambiguous=False, candidate="unanswerable", legal_plan_count=0)
    )

    assert chain["contract_id"] == "qasper_causal_evidence_chain.v1"
    assert chain["status"] == "complete"
    assert chain["incompleteness_reasons"] == []
    assert chain["first_decisive_transition"]["stage"] == "plan_construction"
    assert chain["first_decisive_transition"]["decision"] == ("no_legal_evidence_plan")
    assert chain["first_decisive_transition"]["classification"] == (
        "unexpected_unresolved"
    )
    assert len(chain["first_decisive_transition"]["observation_digest"]) == 64
    recovery = next(stage for stage in chain["stages"] if stage["stage"] == "recovery")
    assert recovery["status"] == "observed"
    assert recovery["cause_stage"] == "plan_construction"
    assert len(recovery["cause_observation_digest"]) == 64


def test_ambiguity_changes_interpretation_not_the_recorded_stage() -> None:
    chain = qasper_causal_evidence_chain(
        _row(ambiguous=True, candidate="unanswerable", legal_plan_count=0)
    )

    assert chain["status"] == "complete"
    assert chain["first_decisive_transition"]["stage"] == "plan_construction"
    assert chain["first_decisive_transition"]["classification"] == (
        "expected_ambiguity_unresolved"
    )


def test_missing_crosswalk_fails_trace_completeness_closed() -> None:
    row = _row(ambiguous=False, candidate="unanswerable", legal_plan_count=0)
    del row["semantic_verifier"]["semantic_data_lineage"]["source_packing"][
        "selector_crosswalk"
    ]

    chain = qasper_causal_evidence_chain(row)

    assert chain["status"] == "incomplete"
    assert "selector_crosswalk_missing" in chain["incompleteness_reasons"]
    assert chain["first_decisive_transition"]["stage"] == "trace_contract"


def test_unanswerable_despite_a_legal_plan_is_the_first_decisive_transition() -> None:
    chain = qasper_causal_evidence_chain(
        _row(ambiguous=False, candidate="unanswerable", legal_plan_count=1)
    )

    assert chain["status"] == "complete"
    assert chain["first_decisive_transition"]["stage"] == "candidate_generation"
    assert chain["first_decisive_transition"]["decision"] == (
        "unanswerable_despite_legal_local_plan"
    )
    assert chain["first_decisive_transition"]["classification"] == (
        "unexpected_candidate_decision"
    )


def test_tampered_source_decisions_digest_fails_closed() -> None:
    row = _row(ambiguous=False, candidate="unanswerable", legal_plan_count=0)
    row["semantic_verifier"]["semantic_data_lineage"]["source_packing"][
        "source_decisions_digest"
    ] = ("0" * 64)

    chain = qasper_causal_evidence_chain(row)

    assert chain["status"] == "incomplete"
    assert "source_or_window_decisions_incomplete" in chain["incompleteness_reasons"]
    assert "source_decisions_digest_mismatch" in chain["incompleteness_reasons"]


def test_pre_model_prefix_accepts_complete_recorded_trace() -> None:
    row = _row(ambiguous=False, candidate="unanswerable", legal_plan_count=0)

    assert qasper_causal_evidence_chain_prefix_complete(row) is True
