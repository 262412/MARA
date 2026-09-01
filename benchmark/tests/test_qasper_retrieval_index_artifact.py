from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _CODE_SHA,
    _prediction_and_debug_row,
    _run_context,
    _transaction,
)
from scripts.slurm.qasper_retrieval_index_artifact import (
    audit_retrieval_index_binding,
    build_retrieval_index_artifact,
)
from scripts.slurm.qasper_retrieval_index_snapshot import (
    build_retrieval_index_restore_audit,
    index_snapshot_manifest,
)


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


def test_stage2_artifact_freezes_raw_records_ranking_and_digests() -> None:
    transaction = _transaction()

    artifact = _artifact(transaction)
    binding = audit_retrieval_index_binding(
        artifact,
        [_trace(transaction)],
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
        required_route="text_rag",
    )

    record = artifact["stage2_records"][0]
    payload = transaction["stages"][1]["payload"]
    assert record["raw_retrieval_records"] == payload["raw_retrieval_records"]
    assert record["ranking"] == payload["ranking"]
    assert (
        record["raw_retrieval_records_digest"]
        == payload["raw_retrieval_records_digest"]
    )
    assert record["ranking_digest"] == payload["ranking_digest"]
    assert (
        record["stage_comparison_digest"]
        == transaction["stages"][1]["comparison_digest"]
    )
    assert binding["status"] == "matched"
    assert binding["matched_record_count"] == 1
    assert binding["violations"] == []


def test_stage2_artifact_rejects_changed_raw_records_before_later_stages() -> None:
    artifact = _artifact(_transaction())
    prediction, debug_row = _prediction_and_debug_row()
    prediction["retrieved_hits"][0]["text"] = "Different online retrieval record."
    online = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
        origin="online",
    )

    binding = audit_retrieval_index_binding(
        artifact,
        [_trace(online)],
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
        required_route="text_rag",
    )

    assert binding["status"] == "failed"
    assert binding["matched_record_count"] == 0
    assert binding["observations"] == [
        {
            "example_id": "example-1",
            "route": "text_rag",
            "status": "diverged",
            "first_divergence": {
                "stage_index": 2,
                "stage": "retrieval_and_ranking",
                "reason": "raw_retrieval_records_mismatch",
                "producer_digest": artifact["stage2_records"][0][
                    "raw_retrieval_records_digest"
                ],
                "validator_digest": online["stages"][1]["payload"][
                    "raw_retrieval_records_digest"
                ],
                "serializer_identity": "canonical_json_utf8_v1",
            },
            "later_stages_evaluated": False,
        }
    ]


def test_old_snapshot_cannot_prove_current_online_path_equivalence() -> None:
    transaction = _transaction()
    artifact = _artifact(transaction)
    old_artifact = deepcopy(artifact)
    old_artifact["code_sha"] = "7" * 40

    binding = audit_retrieval_index_binding(
        old_artifact,
        [_trace(transaction)],
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
        required_route="text_rag",
    )

    assert binding["status"] == "failed"
    assert binding["matched_record_count"] == 0
    assert binding["observations"] == []
    assert binding["violations"] == [
        "retrieval_index_artifact_integrity_invalid:artifact_digest_mismatch",
        "retrieval_index_artifact_code_sha_mismatch",
    ]


def test_stage2_binding_rejects_runtime_contract_drift_before_rows() -> None:
    transaction = _transaction()
    artifact = _artifact(transaction)

    binding = audit_retrieval_index_binding(
        artifact,
        [_trace(transaction)],
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "9" * 64,
        expected_embedding_contract="8" * 64,
        required_route="text_rag",
    )

    assert binding["status"] == "failed"
    assert binding["observations"] == []
    assert binding["matched_record_count"] == 0
    assert binding["violations"] == [
        "retrieval_index_artifact_index_contract_mismatch",
        "retrieval_index_artifact_embedding_contract_mismatch",
    ]


def test_restore_audit_proves_the_consumed_physical_snapshot(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "index.sqlite").write_bytes(b"frozen-index")
    artifact = build_retrieval_index_artifact(
        [_trace(_transaction())],
        code_sha=_CODE_SHA,
        index_contract="sha256:" + "2" * 64,
        embedding_contract="3" * 64,
        index_snapshot=index_snapshot_manifest(snapshot),
        source_artifacts={
            "predictions": {"path": "/predictions", "sha256": "5" * 64},
            "semantic_debug_traces": {"path": "/traces", "sha256": "6" * 64},
        },
    )

    restore = build_retrieval_index_restore_audit(
        artifact,
        snapshot_path=snapshot,
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
    )

    assert restore["status"] == "matched"
    assert restore["artifact_digest"] == artifact["artifact_digest"]
    assert (
        restore["expected_snapshot_tree_digest"]
        == restore["observed_snapshot_tree_digest"]
    )
    assert restore["violations"] == []


def test_restore_audit_fails_closed_on_physical_snapshot_drift(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    index = snapshot / "index.sqlite"
    index.write_bytes(b"frozen-index")
    artifact = build_retrieval_index_artifact(
        [_trace(_transaction())],
        code_sha=_CODE_SHA,
        index_contract="sha256:" + "2" * 64,
        embedding_contract="3" * 64,
        index_snapshot=index_snapshot_manifest(snapshot),
        source_artifacts={
            "predictions": {"path": "/predictions", "sha256": "5" * 64},
            "semantic_debug_traces": {"path": "/traces", "sha256": "6" * 64},
        },
    )
    index.write_bytes(b"different-index")

    restore = build_retrieval_index_restore_audit(
        artifact,
        snapshot_path=snapshot,
        expected_code_sha=_CODE_SHA,
        expected_index_contract="sha256:" + "2" * 64,
        expected_embedding_contract="3" * 64,
    )

    assert restore["status"] == "failed"
    assert "retrieval_index_snapshot_tree_digest_mismatch" in restore["violations"]
