from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.qasper_causal_transaction_stages import (
    _retrieval_payload,
    retrieval_trace_semantic_projection,
    retrieval_trace_telemetry_projection,
    stage_comparison_payload,
)
from benchmark.tests.test_qasper_causal_transaction import (
    _CODE_SHA,
    _prediction_and_debug_row,
    _run_context,
    _transaction,
)
from scripts.slurm.qasper_retrieval_index_artifact import (
    _compare_stage2_record,
    audit_retrieval_index_binding,
    build_retrieval_index_artifact,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qasper_stage2_10398536_retrieval_trace_pairs.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _trace_with_seconds(case: dict, field: str) -> list[dict]:
    trace = deepcopy(case["semantic_trace"])
    for measurement in case[field]:
        item = trace[measurement["trace_index"]]
        assert item["stage"] == measurement["stage"]
        item["seconds"] = measurement["seconds"]
    return trace


def _trace(transaction: dict) -> dict:
    key = transaction["transaction_key"]
    return {
        "example_id": key["example_id"],
        "route": key["route"],
        "causal_transaction": transaction,
    }


def _artifact(transaction: dict) -> dict:
    return build_retrieval_index_artifact(
        [_trace(transaction)],
        code_sha=_CODE_SHA,
        index_contract="sha256:" + "2" * 64,
        embedding_contract="3" * 64,
        index_snapshot={
            "contract_id": "qasper_index_snapshot.v1",
            "path": "/artifacts/qasper-index",
            "tree_digest": "4" * 64,
            "file_count": 3,
            "total_bytes": 1024,
        },
        source_artifacts={
            "predictions": {
                "path": "/artifacts/predictions.jsonl",
                "sha256": "5" * 64,
            },
            "semantic_debug_traces": {
                "path": "/artifacts/semantic_debug_traces.jsonl",
                "sha256": "6" * 64,
            },
        },
    )


def _refresh_trace_digests(record: dict) -> None:
    trace = record["retrieval_trace"]
    record["retrieval_trace_digest"] = canonical_digest(trace)
    record["retrieval_trace_semantic_digest"] = canonical_digest(
        retrieval_trace_semantic_projection(trace)
    )
    record["retrieval_trace_telemetry_digest"] = canonical_digest(
        retrieval_trace_telemetry_projection(trace)
    )


def test_six_real_trace_pairs_differ_only_in_preserved_seconds() -> None:
    fixture = _fixture()

    assert fixture["contract_id"] == (
        "qasper_stage2_retrieval_trace_characterization.v1"
    )
    assert fixture["producer"]["job_id"] == "10398105"
    assert fixture["validator"]["job_id"] == "10398536"
    assert len(fixture["cases"]) == 6

    for case in fixture["cases"]:
        producer = _trace_with_seconds(case, "producer_seconds")
        validator = _trace_with_seconds(case, "validator_seconds")

        assert producer != validator
        assert canonical_digest(producer) == case["producer_retrieval_trace_digest"]
        assert canonical_digest(validator) == case["validator_retrieval_trace_digest"]
        assert retrieval_trace_semantic_projection(producer) == case["semantic_trace"]
        assert retrieval_trace_semantic_projection(validator) == case["semantic_trace"]
        assert (
            retrieval_trace_telemetry_projection(producer) == case["producer_seconds"]
        )
        assert (
            retrieval_trace_telemetry_projection(validator) == case["validator_seconds"]
        )


def test_stage2_keeps_full_timing_but_compares_the_semantic_trace() -> None:
    reference_prediction, reference_debug = _prediction_and_debug_row()
    replay_prediction, replay_debug = _prediction_and_debug_row()
    reference_prediction["retrieval_trace"][0]["seconds"] = 1.25
    replay_prediction["retrieval_trace"][0]["seconds"] = 9.75
    reference = qasper_causal_transaction(
        reference_prediction,
        reference_debug,
        run_context=_run_context(),
        origin="online",
    )
    replay = qasper_causal_transaction(
        replay_prediction,
        replay_debug,
        run_context=_run_context(),
        origin="online",
    )
    artifact = _artifact(reference)

    binding = audit_retrieval_index_binding(
        artifact,
        [_trace(replay)],
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
        required_route="text_rag",
    )
    reference_stage = reference["stages"][1]
    replay_stage = replay["stages"][1]

    assert reference_stage["payload"]["retrieval_trace"][0]["seconds"] == 1.25
    assert replay_stage["payload"]["retrieval_trace"][0]["seconds"] == 9.75
    assert reference_stage["payload_digest"] != replay_stage["payload_digest"]
    assert reference_stage["comparison_digest"] == replay_stage["comparison_digest"]
    assert binding["status"] == "matched"
    assert binding["matched_record_count"] == 1


def test_stage2_comparison_payload_uses_only_semantic_retrieval_identity() -> None:
    trace = [{"stage": "runtime_turn", "status": "completed", "seconds": 2.5}]
    payload = _retrieval_payload(
        {
            "retrieved_hits": [],
            "retrieval_trace": trace,
            "evidence_bundle": {"items": []},
        }
    )

    comparison = stage_comparison_payload("retrieval_and_ranking", payload)

    assert payload["retrieval_trace"] == trace
    assert payload["retrieval_trace_digest"] == canonical_digest(trace)
    assert payload["retrieval_trace_telemetry_digest"] == canonical_digest(
        [{"trace_index": 0, "stage": "runtime_turn", "seconds": 2.5}]
    )
    assert comparison["retrieval_trace_semantic_digest"] == canonical_digest(
        [{"stage": "runtime_turn", "status": "completed"}]
    )
    assert "retrieval_trace_digest" not in comparison
    assert "retrieval_trace_telemetry_digest" not in comparison


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("record_id", "raw_retrieval_records_mismatch"),
        ("ranking_order", "ranking_mismatch"),
        ("ranking_score", "ranking_mismatch"),
        ("production_input", "production_input_records_mismatch"),
        ("retrieval_semantics", "retrieval_trace_semantic_mismatch"),
    ],
)
def test_stage2_semantic_mutations_still_fail_closed(
    mutation: str,
    reason: str,
) -> None:
    expected = _artifact(_transaction())["stage2_records"][0]
    observed = deepcopy(expected)

    if mutation == "record_id":
        observed["raw_retrieval_records"][0]["canonical_id"] = "different-record"
        observed["raw_retrieval_records_digest"] = canonical_digest(
            observed["raw_retrieval_records"]
        )
    elif mutation == "ranking_order":
        observed["ranking"].append(
            {
                "position": 0,
                "canonical_id": "different-record",
                "reranker_rank": 0,
                "reranker_score": 1.0,
            }
        )
        observed["ranking"].reverse()
        observed["ranking_digest"] = canonical_digest(observed["ranking"])
    elif mutation == "ranking_score":
        observed["ranking"][0]["reranker_score"] = 0.1
        observed["ranking_digest"] = canonical_digest(observed["ranking"])
    elif mutation == "production_input":
        observed["production_input_records"][0]["text"] = "Different input."
        observed["production_input_records_digest"] = canonical_digest(
            observed["production_input_records"]
        )
    else:
        observed["retrieval_trace"][0]["status"] = "different"
        _refresh_trace_digests(observed)

    comparison = _compare_stage2_record(expected, observed)

    assert comparison["status"] == "diverged"
    assert comparison["first_divergence"]["stage_index"] == 2
    assert comparison["first_divergence"]["reason"] == reason
    assert comparison["later_stages_evaluated"] is False
