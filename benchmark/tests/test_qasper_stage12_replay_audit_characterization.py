from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transaction_prefix,
    compare_qasper_causal_transactions,
)
from benchmark.qasper_causal_transaction_stages import stage_comparison_payload
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows
from benchmark.tests.qasper_terminal_projection_fixture import (
    attach_valid_terminal_projection,
)
from benchmark.tests.test_qasper_natural_semantic_pack_probe import _row
from scripts.slurm.qasper_causal_transaction_gate import (
    qasper_causal_transaction_artifact_audit,
)
from scripts.slurm.qasper_natural_semantic_pack_audit import build_audit

# These are the six sample IDs and three routes in the focused 6x3 quality run
# that motivated this gate.  The run had complete online transactions but no
# per-row qasper_natural_causal_transaction_replay.v1 records.
_LATEST_RUN_SHA = "6fb1d7ae9a92f3c525b88be2775c05e423f2c56f"
_LATEST_SAMPLE_IDS = (
    "e330e162ec29722f5ec9f83853d129c9e0693d65",
    "6568a31241167f618ef5ede939053feaa2fb0d7e",
    "f2155dc4aeab86bf31a838c8ff388c85440fce6e",
    "7cd22ca9e107d2b13a7cc94252aaa9007976b338",
    "25c1c4a91f5dedd4e06d14121af3b5921db125e9",
    "e97186c51d4af490dba6faaf833d269c8256426c",
)
_LATEST_ROUTES = ("text_rag", "controller_auto", "crag_guarded")
_REPLAY_CONTRACT = "qasper_natural_causal_transaction_replay.v1"


def _quality_predictions() -> list[dict[str, Any]]:
    predictions = []
    for index, example_id in enumerate(_LATEST_SAMPLE_IDS, start=1):
        for route in _LATEST_ROUTES:
            prediction: dict[str, Any] = dict(_row())
            prediction["example_id"] = example_id
            prediction["route"] = route
            prediction["evidence_bundle"]["route"] = route
            attach_valid_terminal_projection(
                prediction,
                answer=str(prediction.get("answer_for_scoring") or "unanswerable"),
            )
            predictions.append(prediction)
    return predictions


def _semantic_traces(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traces = qasper_semantic_debug_rows(
        predictions,
        include_missing=True,
        run_context={
            "worktree_path": "/fixture/worktree",
            "run_provenance": {
                "git": {"commit": _LATEST_RUN_SHA, "dirty": False},
                "manifest": {
                    "path": "/fixture/manifest.json",
                    "sha256": "b" * 64,
                },
                "config": {"suite": "qasper_debug"},
            },
            "backend_metadata": {
                route: {"model": "Qwen/Qwen3-8B"} for route in _LATEST_ROUTES
            },
        },
    )
    assert len(traces) == 18
    assert all(trace["causal_transaction"]["status"] == "complete" for trace in traces)
    assert all(
        trace["causal_transaction"]["stages"][11]["status"] == "complete"
        for trace in traces
    )
    return traces


def _write_traces(
    run_dir: Path,
    traces: list[dict[str, Any]],
    *,
    artifact_complete: bool = True,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "semantic_debug_traces.jsonl").write_text(
        "".join(json.dumps(trace, sort_keys=True) + "\n" for trace in traces),
        encoding="utf-8",
    )
    if artifact_complete:
        (run_dir / "artifact_complete.json").write_text(
            json.dumps({"complete": True}) + "\n",
            encoding="utf-8",
        )


def _rechain(transaction: dict[str, Any]) -> None:
    previous = ""
    for stage in transaction["stages"]:
        payload = stage["payload"]
        stage["payload_digest"] = canonical_digest(payload)
        stage["comparison_digest"] = canonical_digest(
            stage_comparison_payload(stage["stage"], payload)
        )
        stage["previous_chain_digest"] = previous
        stage["chain_digest"] = canonical_digest(
            {
                "stage_index": stage["stage_index"],
                "stage": stage["stage"],
                "payload_digest": stage["payload_digest"],
                "previous_chain_digest": previous,
            }
        )
        previous = stage["chain_digest"]
    transaction["terminal_chain_digest"] = previous
    transaction_digest_payload = {
        key: value for key, value in transaction.items() if key != "transaction_digest"
    }
    transaction["transaction_digest"] = canonical_digest(transaction_digest_payload)


def _replay_record(
    trace: dict[str, Any],
    *,
    through_stage: int = 12,
    divergence_stage: int | None = None,
    identity_key: tuple[str, str] | None = None,
) -> dict[str, Any]:
    reference = deepcopy(trace["causal_transaction"])
    local = deepcopy(reference)
    if divergence_stage is not None:
        local["stages"][divergence_stage - 1]["payload"][
            "characterization_mutation"
        ] = "local-only"
        _rechain(local)
    if identity_key is not None:
        reference["transaction_key"] = {
            "example_id": identity_key[0],
            "route": identity_key[1],
        }
    if through_stage == len(QASPER_CAUSAL_TRANSACTION_STAGES):
        comparison = compare_qasper_causal_transactions(reference, local)
    else:
        comparison = compare_qasper_causal_transaction_prefix(
            reference,
            local,
            through_stage=through_stage,
        )
    return {
        "contract_id": _REPLAY_CONTRACT,
        "status": (
            "matched"
            if comparison["status"] in {"matched", "matched_prefix"}
            else "failed"
        ),
        "comparison_scope": (
            "causal_replay_through_"
            f"{QASPER_CAUSAL_TRANSACTION_STAGES[through_stage - 1]}"
        ),
        "through_stage_index": through_stage,
        "through_stage": QASPER_CAUSAL_TRANSACTION_STAGES[through_stage - 1],
        "hard_rule": "stop_at_first_divergence",
        "reference_transaction": reference,
        "local_replay_transaction": local,
        "comparison": comparison,
    }


def _replayed_quality_rows(
    *,
    through_stage: int = 12,
    divergence_stage: int | None = None,
    identity_key: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predictions = _quality_predictions()
    traces = _semantic_traces(predictions)
    for trace, prediction in zip(traces, predictions):
        replay = _replay_record(
            trace,
            through_stage=through_stage,
            divergence_stage=(
                divergence_stage
                if trace["example_id"] == _LATEST_SAMPLE_IDS[0]
                and trace["route"] == _LATEST_ROUTES[0]
                else None
            ),
            identity_key=(
                identity_key
                if trace["example_id"] == _LATEST_SAMPLE_IDS[0]
                and trace["route"] == _LATEST_ROUTES[0]
                else None
            ),
        )
        trace["causal_transaction_replay"] = replay
        prediction["causal_transaction_replay"] = deepcopy(replay)
    return predictions, traces


def _natural_audit_rows(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "example_id": str(prediction["example_id"]),
            "route": str(prediction["route"]),
            "status": "passed",
            "code_sha": _LATEST_RUN_SHA,
            "no_policy_cohorts": [
                "auditable_no",
                "closed_world_no",
                "annotation_disagreement",
            ],
            "ambiguity": {"denominator": "unambiguous"},
            "causal_transaction_replay": deepcopy(
                prediction["causal_transaction_replay"]
            ),
        }
        for prediction in predictions
    ]


def _natural_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return build_audit(
        rows,
        code_sha=_LATEST_RUN_SHA,
        input_path=Path(__file__),
        expected_count=18,
    )


def test_stage12_gate_replays_complete_artifact_and_reports_18_matches(
    tmp_path: Path,
) -> None:
    predictions = _quality_predictions()
    traces = _semantic_traces(predictions)
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["expected_transaction_count"] == 18
    assert audit["observed_transaction_count"] == 18
    # No replay is pre-attached: the formal gate must reconstruct it from the
    # frozen candidate-stage snapshot and the online reference transaction.
    assert audit["complete_transaction_count"] == 18
    assert audit["replay_matched_transaction_count"] == 18
    assert audit["replay_expected_transaction_count"] == 18
    assert audit["status"] == "passed"
    assert violations == []
    assert all(
        observation["replay_contract_id"] == _REPLAY_CONTRACT
        and observation["status"] == "matched"
        and observation["compared_stage_count"] == 12
        for observation in audit["observations"]
    )


def test_stage12_gate_requires_each_replay_to_reach_stage12(tmp_path: Path) -> None:
    predictions, traces = _replayed_quality_rows(through_stage=11)
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["status"] == "failed"
    assert any(
        "stage" in violation or "prefix" in violation or "replay" in violation
        for violation in violations
    )


def test_stage12_gate_requires_exact_sample_route_replay_identity(
    tmp_path: Path,
) -> None:
    predictions, traces = _replayed_quality_rows(
        identity_key=("wrong-sample", "wrong-route")
    )
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["status"] == "failed"
    assert any(
        "identity" in violation or "key" in violation for violation in violations
    )


def test_stage12_gate_reports_only_the_first_replay_divergence(tmp_path: Path) -> None:
    predictions, traces = _replayed_quality_rows(divergence_stage=8)
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["status"] == "failed"
    assert violations
    observation = audit["observations"][0]
    assert observation["first_divergence"] == {
        "stage_index": 8,
        "stage": "model_response_and_parser",
        "reason": "stage_comparison_digest_mismatch",
    }
    assert observation["later_stages_evaluated"] is False
    assert "later_divergences" not in observation


def test_stage12_gate_does_not_reconstruct_replay_from_a_legacy_snapshot(
    tmp_path: Path,
) -> None:
    predictions = _quality_predictions()
    traces = _semantic_traces(predictions)
    metadata = predictions[0]["evidence_metadata"]
    source = metadata["qasper_canonical_semantic_pack"]["source_packing_observation"]
    source.pop("source_input_snapshot", None)
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["status"] == "failed"
    assert any("replay" in violation for violation in violations)


def test_stage12_gate_does_not_reconstruct_replay_from_an_incomplete_snapshot(
    tmp_path: Path,
) -> None:
    predictions = _quality_predictions()
    traces = _semantic_traces(predictions)
    candidate = predictions[0]["evidence_metadata"]["qasper_candidate_generation"]
    candidate["candidate_request_projection_trace"]["complete"] = False
    _write_traces(tmp_path, traces)

    audit, violations = qasper_causal_transaction_artifact_audit(
        tmp_path,
        predictions,
        suite_kind="qasper_debug",
    )

    assert audit["status"] == "failed"
    assert any("replay" in violation for violation in violations)


def test_natural_replay_audit_reuses_the_transaction_replay_contract() -> None:
    predictions, _traces = _replayed_quality_rows()
    audit = _natural_audit(_natural_audit_rows(predictions))

    assert audit["prediction_count"] == 18
    assert audit["status"] == "passed"
    replay_audit = audit["causal_transaction_replay_audit"]
    assert replay_audit["contract_id"] == "qasper_natural_causal_replay_audit.v1"
    assert replay_audit["replay_contract_id"] == _REPLAY_CONTRACT
    observations = replay_audit["observations"]
    assert len(observations) == 18
    assert {
        (observation["example_id"], observation["route"])
        for observation in observations
    } == {
        (example_id, route)
        for example_id in _LATEST_SAMPLE_IDS
        for route in _LATEST_ROUTES
    }
    assert all(observation["status"] == "matched" for observation in observations)
    assert all(
        observation["compared_stage_count"] == 12 for observation in observations
    )
    assert all(
        observation["later_stages_evaluated"] is True for observation in observations
    )


def test_natural_replay_audit_rejects_duplicate_sample_route_keys() -> None:
    predictions, _traces = _replayed_quality_rows()
    rows = _natural_audit_rows(predictions)
    rows[1]["example_id"] = rows[0]["example_id"]
    rows[1]["route"] = rows[0]["route"]

    audit = _natural_audit(rows)

    assert audit["status"] == "failed"


def test_natural_replay_audit_reports_first_divergence_without_later_stages() -> None:
    predictions, _traces = _replayed_quality_rows(divergence_stage=8)
    audit = _natural_audit(_natural_audit_rows(predictions))

    assert audit["status"] == "failed"
    observation = audit["causal_transaction_replay_audit"]["observations"][0]
    assert observation["status"] == "failed"
    assert observation["compared_stage_count"] == 7
    assert observation["first_divergence"]["stage_index"] == 8
    assert observation["first_divergence"]["stage"] == "model_response_and_parser"
    assert observation["later_stages_evaluated"] is False
    assert "later_divergences" not in observation
