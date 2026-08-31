from __future__ import annotations

from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    qasper_canonical_span_universe_digest,
)

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)


def test_selector_stage_reads_full_spans_from_the_immutable_pack() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    selector = {
        "selector_id": "E1:S1",
        "text": "The authors compared systems.",
        "span_start": 0,
        "span_end": 29,
        "canonical_start": 0,
        "canonical_end": 29,
        "allowed_proposition_slots": ["actor", "predicate", "object"],
        "proposition_slot_spans": {},
        "relation_bearing": True,
        "candidate_relation_role": "support",
        "local_relation_state": "support",
        "local_relation_analysis_digest": "2" * 64,
        "event_id": "event-1",
        "object_tokens": ["systems"],
        "event_core_tokens": ["authors", "compared", "systems"],
        "predicate_match_kind": "exact",
        "semantic_alignment": {},
    }
    records = [{"evidence_id": "evidence-1", "selectors": [selector]}]
    span_digest = qasper_canonical_span_universe_digest(records)
    pack_digest = "4" * 64
    transaction_id = "5" * 64
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    pack.update(
        {
            "contract_id": QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
            "semantic_pack_digest": pack_digest,
            "span_universe_digest": span_digest,
            "candidate_transaction_id": transaction_id,
            "records": records,
        }
    )
    debug_row["main_candidate_generator"].update(
        {
            "evidence_pack_digest": pack_digest,
            "canonical_semantic_pack_contract_id": (
                QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT
            ),
            "canonical_semantic_pack_digest": pack_digest,
            "canonical_span_universe_digest": span_digest,
            "canonical_pack_candidate_transaction_id": transaction_id,
        }
    )

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][3]

    assert stage["status"] == "complete"
    assert stage["payload"]["canonical_records"] == records
    assert stage["payload"]["proposition_bearing_spans"] == [
        {"evidence_id": "evidence-1", **selector}
    ]
    assert stage["payload"]["selector_universe_digest"] == span_digest
    assert stage["payload"]["recomputed_selector_universe_digest"] == span_digest


def test_selector_stage_fails_closed_without_pack_records_or_identity() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    for field in (
        "contract_id",
        "semantic_pack_digest",
        "span_universe_digest",
        "candidate_transaction_id",
        "records",
    ):
        pack.pop(field, None)
    for field in (
        "evidence_pack_digest",
        "canonical_semantic_pack_contract_id",
        "canonical_semantic_pack_digest",
        "canonical_span_universe_digest",
        "canonical_pack_candidate_transaction_id",
    ):
        debug_row["main_candidate_generator"].pop(field, None)

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][3]

    assert stage["status"] == "incomplete"
    assert "canonical_records_missing" in stage["incompleteness_reasons"]
    assert "proposition_bearing_spans_missing" in stage["incompleteness_reasons"]
    assert "generator_canonical_span_universe_digest_missing" in (
        stage["incompleteness_reasons"]
    )
