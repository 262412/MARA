from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from benchmark.qasper_golden_replay import (
    ANCHOR_REPLAY_SHA256,
    REQUIRED_ROW_FIELDS,
    build_golden_contract,
    build_protected_sets,
    legacy_prediction_projection_hash,
    project_prediction,
    projection_sha256,
    read_projection_jsonl,
    validate_golden_fixture,
)

FIXTURE_DIR = Path(__file__).with_name("fixtures")
ROWS_FIXTURE = FIXTURE_DIR / "qasper_golden_replay_v1.jsonl"
CONTRACT_FIXTURE = FIXTURE_DIR / "qasper_golden_replay_v1.json"


def _evidence(runtime_source: str, runtime_id: str) -> dict[str, Any]:
    return {
        "evidence_id": runtime_id,
        "canonical_id": f"evidence:{runtime_source}:{runtime_id}",
        "source_id": runtime_source,
        "runtime_source_id": runtime_source,
        "evaluation_source_id": "paper-1",
        "document_id": "paper-1",
        "normalized_text_hash": "stable-text-hash",
        "text": "The authors evaluated the method on clinical tasks.",
        "metadata": {
            "source_id": runtime_source,
            "evaluation_source_id": "paper-1",
            "document_id": "paper-1",
        },
    }


def _typed_authority(evidence_ref: str, quote: str) -> dict[str, Any]:
    return {
        "contract_id": "typed_proposition_authority.v1",
        "state": "verified_support",
        "reason": "exact_boolean_proposition",
        "answer_type": "boolean",
        "required_slot_ids": ["support:boolean_proposition"],
        "verified_slot_ids": ["support:boolean_proposition"],
        "slot_bindings": {"support:boolean_proposition": [evidence_ref]},
        "authority_atoms": [
            {
                "evidence_id": evidence_ref,
                "evidence_ref": f"{evidence_ref}#quote:0:52",
                "quote": quote,
                "span_start": 0,
                "span_end": 52,
                "actor": "current_paper",
                "relation": "evaluate",
                "object": "clinical tasks",
                "polarity": "yes",
                "scope": "experiments",
            }
        ],
        "canonical_answer_polarity": "yes",
    }


def _prediction(
    runtime_source: str,
    runtime_id: str,
    *,
    example_id: str = "example-1",
    route: str = "text_rag",
    answer_status: str = "answered",
    native_score: float = 1.0,
    true_abstention: int = 0,
) -> dict[str, Any]:
    evidence = _evidence(runtime_source, runtime_id)
    evidence_ref = f"evidence:{runtime_source}:{runtime_id}"
    typed_authority = _typed_authority(evidence_ref, str(evidence["text"]))
    return {
        "example_id": example_id,
        "route": route,
        "benchmark_question": "Did the authors evaluate on clinical tasks?",
        "benchmark_retrieval_query": "Did the authors evaluate on clinical tasks?",
        "answer_status": answer_status,
        "answer_for_scoring": "yes" if answer_status == "answered" else "unanswerable",
        "answer_for_user": "Yes." if answer_status == "answered" else "unanswerable",
        "metrics": {"native_score": native_score},
        "retrieved_hits": [evidence],
        "evidence_metadata": {
            "candidate_evidence": [evidence],
            "reranker_input_evidence": [evidence],
            "reranked_evidence": [evidence],
            "selected_evidence": [evidence],
            "verification_slot_states": [
                {
                    "slot_id": "support:boolean_proposition",
                    "status": "verified_support",
                    "evidence_ids": [evidence_ref],
                }
            ],
            "typed_authority": typed_authority,
        },
        "engine_verify_decision": {
            "mode": "strict",
            "status": "supported",
            "action": "generate",
            "reason": "exact support",
            "boolean_authority_status": "verified_support",
            "canonical_answer_polarity": "yes",
            "authoritative_evidence_id": evidence_ref,
            "authoritative_evidence_ref": f"{evidence_ref}#quote:0:52",
            "authoritative_quote": evidence["text"],
            "verified_support_slot_ids": ["support:boolean_proposition"],
            "typed_authority": typed_authority,
        },
        "guardrail_decision": {
            "status": "ok",
            "action": "return",
            "reason": "exact support",
        },
        "terminal_semantic_commit": {
            "contract_id": "terminal_semantic_commit.v3",
            "semantic_answer": "yes",
            "presentation_answer": "Yes.",
            "answer_status": answer_status,
            "outcome": "answered" if answer_status == "answered" else "safe_abstention",
            "outcome_reason": "verified_support",
            "projection_hash": "source-projection-hash",
        },
        "terminal_outcome": (
            "answered" if answer_status == "answered" else "safe_abstention"
        ),
        "terminal_outcome_reason": "verified_support",
        "engine_terminal_projection_hash": "engine-projection-hash",
        "verifier_observability": {
            "true_abstention": true_abstention,
            "false_abstention": int(
                answer_status == "abstained" and not true_abstention
            ),
            "retry_count": 2,
            "retrieval_retry_count": 1,
            "verifier_recovery_count": 1,
            "route_switch_count": 0,
        },
    }


def _projected(
    run_label: str,
    example_id: str,
    *,
    answer_status: str,
    native_score: float,
    true_abstention: int,
) -> dict[str, Any]:
    prediction = _prediction(
        "11111111-1111-4111-8111-111111111111",
        f"stable-{example_id}",
        example_id=example_id,
        answer_status=answer_status,
        native_score=native_score,
        true_abstention=true_abstention,
    )
    return project_prediction(prediction, run_label=run_label)


def test_projection_ignores_runtime_uuid_but_preserves_all_required_layers() -> None:
    first = project_prediction(
        _prediction(
            "11111111-1111-4111-8111-111111111111",
            "runtime-a",
        ),
        run_label="anchor_0343ba1",
    )
    second = project_prediction(
        _prediction(
            "22222222-2222-4222-8222-222222222222",
            "runtime-b",
        ),
        run_label="anchor_0343ba1",
    )

    assert first == second
    assert set(REQUIRED_ROW_FIELDS) <= set(first)
    assert first["candidate_evidence_identities"] == ["paper-1||||stable-text-hash"]
    assert first["required_slot_states"][0]["evidence_ids"] == [
        "paper-1||||stable-text-hash"
    ]
    assert first["typed_authority"]["state"] == "verified_support"
    assert first["verifier_decision"]["boolean_authority_status"] == (
        "verified_support"
    )
    assert first["control_counts"] == {
        "retrieval_retry_count": 1,
        "retry_count": 2,
        "route_switch_count": 0,
        "verifier_recovery_count": 1,
    }


def test_projection_derives_legacy_outcome_without_hiding_raw_absence() -> None:
    prediction = _prediction("runtime-source", "runtime-evidence")
    prediction.pop("terminal_outcome")
    prediction.pop("terminal_outcome_reason")
    terminal = prediction["terminal_semantic_commit"]
    terminal.pop("outcome")
    terminal.pop("outcome_reason")

    row = project_prediction(prediction, run_label="anchor_0343ba1")

    assert row["raw_terminal_outcome"] is None
    assert row["raw_terminal_outcome_reason"] is None
    assert row["terminal_outcome"] == "answered"
    assert row["terminal_outcome_reason"] == "legacy_answer_status_answered"
    assert row["terminal_outcome_provenance"] == "legacy_derived"


def test_protected_sets_use_explicit_score_and_abstention_predicates() -> None:
    anchor = [
        _projected(
            "anchor_0343ba1",
            "answered",
            answer_status="answered",
            native_score=1.0,
            true_abstention=0,
        ),
        _projected(
            "anchor_0343ba1",
            "negative",
            answer_status="abstained",
            native_score=1.0,
            true_abstention=1,
        ),
        _projected(
            "anchor_0343ba1",
            "recoverable",
            answer_status="abstained",
            native_score=0.0,
            true_abstention=0,
        ),
    ]
    architecture = deepcopy(anchor)
    failed = deepcopy(anchor)
    for rows, label in (
        (architecture, "architecture_fa31e4a"),
        (failed, "failed_520ff98"),
    ):
        for row in rows:
            row["run_label"] = label
        recovered = next(row for row in rows if row["example_id"] == "recoverable")
        recovered.update({"answer_status": "answered", "native_score": 1.0})

    sets = build_protected_sets(
        {
            "anchor_0343ba1": anchor,
            "architecture_fa31e4a": architecture,
            "failed_520ff98": failed,
        }
    )

    assert sets["anchor_correct_answered"]["count"] == 1
    assert sets["architecture_or_failed_new_passing"]["keys"] == [
        ["recoverable", "text_rag"]
    ]
    assert sets["true_abstention_negative"]["keys"] == [["negative", "text_rag"]]


def test_protected_sets_reject_key_or_true_negative_drift() -> None:
    anchor = [
        _projected(
            "anchor_0343ba1",
            "negative",
            answer_status="abstained",
            native_score=1.0,
            true_abstention=1,
        )
    ]
    architecture = deepcopy(anchor)
    failed = deepcopy(anchor)
    architecture[0]["run_label"] = "architecture_fa31e4a"
    failed[0]["run_label"] = "failed_520ff98"
    failed[0]["verifier_observability"]["true_abstention"] = 0

    with pytest.raises(ValueError, match="true-abstention set drift"):
        build_protected_sets(
            {
                "anchor_0343ba1": anchor,
                "architecture_fa31e4a": architecture,
                "failed_520ff98": failed,
            }
        )

    failed = []
    with pytest.raises(ValueError, match="prediction key drift"):
        build_protected_sets(
            {
                "anchor_0343ba1": anchor,
                "architecture_fa31e4a": architecture,
                "failed_520ff98": failed,
            }
        )


def test_legacy_replay_hash_excludes_only_terminal_adapter_fields() -> None:
    rows: list[dict[str, Any]] = [
        {
            "example_id": "example-1",
            "route": "text_rag",
            "metrics": {"native_score": 1.0},
            "terminal_outcome": "answered",
            "terminal_outcome_reason": "verified",
        }
    ]
    changed_adapter = deepcopy(rows)
    changed_adapter[0]["terminal_outcome"] = "safe_abstention"
    changed_score = deepcopy(rows)
    changed_score[0]["metrics"]["native_score"] = 0.0

    assert legacy_prediction_projection_hash(rows) == (
        legacy_prediction_projection_hash(changed_adapter)
    )
    assert legacy_prediction_projection_hash(rows) != (
        legacy_prediction_projection_hash(changed_score)
    )


def test_checked_in_golden_fixture_is_complete_and_immutable() -> None:
    rows = read_projection_jsonl(ROWS_FIXTURE)
    contract = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))

    validate_golden_fixture(rows, contract)

    assert len(rows) == 1431
    assert contract["runs"]["anchor_0343ba1"]["prediction_count"] == 477
    assert contract["runs"]["anchor_0343ba1"]["legacy_replay_sha256"] == (
        ANCHOR_REPLAY_SHA256
    )
    assert contract["protected_sets"]["anchor_correct_answered"]["count"] == 84
    assert (
        contract["protected_sets"]["architecture_or_failed_new_passing"]["count"] == 2
    )
    assert contract["protected_sets"]["true_abstention_negative"]["count"] == 180
    assert contract["answer_status_patterns"] == {
        "AAA": 74,
        "AAX": 4,
        "AXA": 6,
        "XAA": 2,
        "XXX": 391,
    }
    assert contract["runs"]["anchor_0343ba1"]["terminal_outcome_counts"] == {
        "answered": 84,
        "safe_abstention": 393,
    }
    assert contract["protected_sets"]["architecture_or_failed_new_passing"]["keys"] == [
        ["b5608076d91450b0d295ad14c3e3a90d7e168d0e", "crag_guarded"],
        ["b5608076d91450b0d295ad14c3e3a90d7e168d0e", "text_rag"],
    ]


def test_golden_fixture_validation_rejects_projection_tampering() -> None:
    rows = read_projection_jsonl(ROWS_FIXTURE)
    contract = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
    tampered = deepcopy(rows)
    tampered[0]["native_score"] = 0.0

    with pytest.raises(ValueError, match="projection hash mismatch"):
        validate_golden_fixture(tampered, contract)


def test_contract_builder_rejects_duplicate_projection_keys() -> None:
    row = project_prediction(
        _prediction("runtime-source", "runtime-evidence"),
        run_label="anchor_0343ba1",
    )

    with pytest.raises(ValueError, match="duplicate prediction key"):
        build_golden_contract(
            {
                "anchor_0343ba1": [row, deepcopy(row)],
                "architecture_fa31e4a": [{**row, "run_label": "architecture_fa31e4a"}],
                "failed_520ff98": [{**row, "run_label": "failed_520ff98"}],
            },
            legacy_replay_hashes={
                "anchor_0343ba1": "anchor",
                "architecture_fa31e4a": "architecture",
                "failed_520ff98": "failed",
            },
        )


def test_projection_hash_is_order_independent_at_run_boundary() -> None:
    first = _projected(
        "anchor_0343ba1",
        "first",
        answer_status="answered",
        native_score=1.0,
        true_abstention=0,
    )
    second = _projected(
        "anchor_0343ba1",
        "second",
        answer_status="abstained",
        native_score=0.0,
        true_abstention=0,
    )

    assert projection_sha256([first, second]) == projection_sha256([second, first])
