from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from ktem.reasoning.mara_qasper_candidate import _record_candidate_response

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.qasper_causal_transaction_runtime_stages import (
    runtime_transaction_stage_payloads,
)
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)
from benchmark.tests.test_qasper_natural_semantic_pack_probe import _CODE_SHA, _row
from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context


def _row_with_real_raw_response() -> dict[str, Any]:
    row = cast(dict[str, Any], _row())
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    generation = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    identity = {
        key: deepcopy(generation.get(key))
        for key in (
            "trace_group_id",
            "benchmark_route_id",
            "internal_route",
            "transaction_id",
            "attempt_id",
            "generation_sequence",
            "predecessor_transaction_id",
        )
    }
    _record_candidate_response(
        SimpleNamespace(
            text='{\n\n\n    "candidate": "yes"\n}',
            completion_tokens=10,
            prompt_tokens=generation["estimated_input_tokens"],
            finish_reason="stop",
        ),
        generation,
        identity,
        str(generation["input_digest"]),
        "",
    )
    return row


def test_stage_eight_replays_and_reparses_the_frozen_candidate_response() -> None:
    row = _row_with_real_raw_response()
    online = cast(
        dict[str, Any],
        cast(dict[str, Any], row["evidence_metadata"])["qasper_candidate_generation"],
    )
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    local = context.candidate_generation
    for field in (
        "status",
        "failure_reason",
        "raw_response",
        "raw_response_digest",
        "raw_response_truncated",
        "cleaned_response",
        "typed_candidate",
        "typed_candidate_digest",
        "attempts",
    ):
        assert local[field] == online[field]
    assert local["candidate_response_replay"]["status"] == "matched"


def test_stage_eight_rejects_a_tampered_frozen_raw_response_digest() -> None:
    row = _row_with_real_raw_response()
    generation = cast(
        dict[str, Any],
        cast(dict[str, Any], row["evidence_metadata"])["qasper_candidate_generation"],
    )
    generation["raw_response"] = '{"candidate":"no"}'
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    response_replay = context.candidate_generation["candidate_response_replay"]
    assert response_replay["status"] == "failed"
    assert "candidate_raw_response_digest_mismatch" in response_replay["reasons"]


def test_stage_eight_accepts_a_typed_pre_audit_stop_without_a_proposal() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    verifier = debug_row["semantic_verifier"]
    event = verifier["debug_trace"]["events"][0]
    event["transaction"] = {}
    event["outcome"] = {
        "status": "failed",
        "reason": "release_conclusion_auditor_not_independent",
        "audit_status": "not_started",
        "audit_reason": "release_conclusion_auditor_not_independent",
    }
    verifier.update(
        status="failed",
        reason="release_conclusion_auditor_not_independent",
        audit_reason="release_conclusion_auditor_not_independent",
        candidate_verification_status="pre_audit_failed",
        proposal_status="not_started",
        audit_status="not_started",
    )

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][7]

    assert stage["status"] == "complete"
    assert stage["incompleteness_reasons"] == []
    assert stage["payload"]["semantic_proposal"] == {}
    assert stage["payload"]["semantic_audit"] == {}


def test_stage_eight_attempt_digest_ignores_empty_normalization_fields() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    generator = debug_row["main_candidate_generator"]
    normalized_generator = deepcopy(generator)
    normalized_generator["attempts"][0].update(
        provider_failure_reason="",
        provider_failure_detail="",
    )
    verifier = debug_row["semantic_verifier"]
    event = verifier["debug_trace"]["events"][0]
    transaction = event["transaction"]

    reference = runtime_transaction_stage_payloads(
        prediction,
        generator,
        verifier,
        event,
        transaction,
        transaction["proposal"],
        transaction["audit"],
        _run_context(),
    )["model_response_and_parser"]
    normalized = runtime_transaction_stage_payloads(
        prediction,
        normalized_generator,
        verifier,
        event,
        transaction,
        transaction["proposal"],
        transaction["audit"],
        _run_context(),
    )["model_response_and_parser"]

    assert normalized == reference
