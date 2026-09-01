from __future__ import annotations

from copy import deepcopy

from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    qasper_canonical_span_universe_digest,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transaction_prefix,
    compare_qasper_causal_transactions,
    qasper_causal_transaction,
)
from benchmark.tests.qasper_causal_evidence_chain_fixtures import causal_row
from benchmark.tests.qasper_terminal_projection_fixture import (
    attach_valid_terminal_projection,
)

_CODE_SHA = "a" * 40
_MANIFEST_SHA = "b" * 64
_PACK_DIGEST = "4" * 64
_PACK_TRANSACTION_ID = "5" * 64


def _prediction_and_debug_row() -> tuple[dict, dict]:
    debug_row = causal_row(
        ambiguous=False,
        candidate="yes",
        legal_plan_count=1,
    )
    generator = _candidate_generator(debug_row)
    construction = debug_row["semantic_verifier"]["semantic_data_lineage"][
        "plan_construction"
    ]
    construction["selected_plan_id"] = "6" * 64
    proposal_value = _proposal_value()
    debug_row["semantic_verifier"].update(_verifier_trace(proposal_value))
    prediction = _prediction(generator, debug_row)
    debug_row.update(
        {
            "question": prediction["question"],
            "gold_answers": prediction["gold_answers"],
            "qasper_annotation_scores": prediction["qasper_annotation_scores"],
            "qasper_annotation_diagnostics": prediction[
                "qasper_annotation_diagnostics"
            ],
        }
    )
    return prediction, debug_row


def _candidate_generator(debug_row: dict) -> dict:
    generator = debug_row["main_candidate_generator"]
    span_digest = qasper_canonical_span_universe_digest(_canonical_pack_records())
    messages = [
        {"role": "system", "content": "Return one candidate label."},
        {"role": "user", "content": "Did the authors compare systems?"},
    ]
    generator.update(
        {
            "model": "candidate-model:v1",
            "message_stack": messages,
            "message_stack_digest": canonical_digest(messages),
            "response_schema_digest": "3" * 64,
            "estimated_input_tokens": 30,
            "estimated_message_tokens": 20,
            "estimated_schema_tokens": 10,
            "tokenizer_identity": "fixture-tokenizer:v1",
            "tokenizer_method": "fixture_exact",
            "tokenizer_exact": True,
            "tokenizer_endpoint": "fixture://tokenizer",
            "tokenizer_failed": False,
            "tokenizer_failure_reason": "",
            "candidate_input_token_budget": 3920,
            "max_model_len": 4096,
            "max_output_tokens": 48,
            "token_headroom_tokens": 128,
            "candidate_request_dropped_evidence_count": 0,
            "request_dropped_evidence_count": 0,
            "evidence_pack_digest": _PACK_DIGEST,
            "canonical_semantic_pack_contract_id": (
                QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT
            ),
            "canonical_semantic_pack_digest": _PACK_DIGEST,
            "canonical_span_universe_digest": span_digest,
            "canonical_pack_candidate_transaction_id": _PACK_TRANSACTION_ID,
            "candidate_request_projection_trace": _candidate_request_projection(),
            "raw_response": '{"candidate":"yes"}',
            "cleaned_response": '{"candidate":"yes"}',
            "raw_response_truncated": False,
            "attempts": [
                {
                    "attempt_id": "candidate-attempt-1",
                    "raw_response": '{"candidate":"yes"}',
                    "parsed_value": {"candidate": "yes"},
                    "parse_failure_reason": "",
                    "provider_failure_reason": "",
                }
            ],
        }
    )
    return generator


def _candidate_request_projection() -> dict:
    decisions = [
        {
            "evidence_id": "evidence-1",
            "selected": True,
            "decision": "selected_for_model_request",
        }
    ]
    attempts = [
        {
            "record_ids": ["evidence-1"],
            "estimated_input_tokens": 30,
            "tokenizer_failed": False,
            "decision": "accepted",
            "dropped_evidence_id": "",
        }
    ]
    return {
        "contract_id": "qasper_candidate_request_projection.v1",
        "complete": True,
        "input_record_count": 1,
        "selected_record_count": 1,
        "decision_count": 1,
        "decisions_digest": canonical_digest(decisions),
        "decisions": decisions,
        "attempt_count": 1,
        "attempts_digest": canonical_digest(attempts),
        "attempts": attempts,
    }


def _proposal_value() -> dict:
    return {
        "candidate_judgment": "supported",
        "canonical_evidence_plan_id": "6" * 64,
        "premises": [
            {
                "premise_ref": "P1",
                "span_selector": "E1:S1",
                "binds_proposition_slots": ["actor", "predicate", "object"],
                "proposition_slot_bindings": {
                    "actor": "current_paper",
                    "predicate": "compare",
                    "object": "systems",
                },
                "evidence_relation": "proposition_support",
            }
        ],
        "proof_mode": "atomic_semantic",
        "evidence_relation": "proposition_support",
    }


def _verifier_trace(proposal_value: dict) -> dict:
    proposal_input = {
        "prompt": "candidate-bound verifier prompt",
        "question": "Did the authors compare systems?",
        "packed_evidence": [{"evidence_id": "evidence-1", "text": "evidence"}],
        "required_slots": [{"slot_id": "support:boolean_proposition"}],
    }
    audit_input = {
        "prompt": "independent auditor prompt",
        "candidate_proposal": proposal_value,
        "premise_slot_evidence": {"P1": {"actor": "the authors"}},
    }
    transaction = _model_transaction(proposal_value, proposal_input, audit_input)
    return {
        "model": "verifier-model:v2",
        "audit_model": "auditor-model:v3",
        "candidate_verification_status": "supported",
        "proof_mode": "atomic_semantic",
        "debug_trace": {
            "contract_id": "semantic_proposition_debug_trace.v3",
            "event_count": 1,
            "dropped_event_count": 0,
            "events": [
                {
                    "event": "model_transaction",
                    "event_index": 1,
                    "question": "Did the authors compare systems?",
                    "packed_evidence": proposal_input["packed_evidence"],
                    "required_slots": proposal_input["required_slots"],
                    "outcome": {
                        "status": "parsed",
                        "verdict": "yes",
                        "proof_mode": "atomic_semantic",
                    },
                    "transaction": transaction,
                }
            ],
        },
    }


def _model_transaction(
    proposal_value: dict,
    proposal_input: dict,
    audit_input: dict,
) -> dict:
    return {
        "contract_id": "semantic_proposition_debug_trace.v3",
        "transaction_id": "verifier-transaction-1",
        "proposal_model": "verifier-model:v2",
        "audit_model": "auditor-model:v3",
        "proposal_input": proposal_input,
        "proposal_input_digest": canonical_digest(proposal_input),
        "audit_input": audit_input,
        "audit_input_digest": canonical_digest(audit_input),
        "proposal": {
            "status": "parsed",
            "attempts": [
                {
                    "attempt_id": "proposal-attempt-1",
                    "raw_response": (
                        '{"candidate_judgment":"supported",'
                        '"canonical_evidence_plan_id":"' + "6" * 64 + '"}'
                    ),
                    "raw_response_truncated": False,
                    "parsed_value": proposal_value,
                    "parse_failure_reason": "",
                    "provider_failure_reason": "",
                }
            ],
        },
        "audit": {
            "status": "parsed",
            "attempts": [
                {
                    "attempt_id": "audit-attempt-1",
                    "raw_response": '{"jointly_entails":true}',
                    "raw_response_truncated": False,
                    "parsed_value": {"jointly_entails": True},
                    "parse_failure_reason": "",
                    "provider_failure_reason": "",
                }
            ],
        },
    }


def _prediction(generator: dict, debug_row: dict) -> dict:
    source_packing = debug_row["semantic_verifier"]["semantic_data_lineage"][
        "source_packing"
    ]
    prediction = {
        "example_id": "example-1",
        "route": "text_rag",
        "question": "Did the authors compare systems?",
        "document_id": "paper-1",
        "document_ids": ["paper-1"],
        "gold_answers": ["yes"],
        "gold_evidence": [
            {"document_id": "paper-1", "span": "The authors compared systems."}
        ],
        "retrieval_trace": [{"stage": "retrieval", "status": "completed"}],
        "retrieved_hits": [
            {
                "canonical_id": "evidence-1",
                "text": "The authors compared systems.",
                "reranker_rank": 1,
                "reranker_score": 0.9,
            }
        ],
        "evidence_bundle": {
            "items": [
                {
                    "canonical_id": "evidence-1",
                    "text": "The authors compared systems.",
                }
            ]
        },
        "evidence_metadata": {
            "candidate_ranked_evidence": [{"canonical_id": "evidence-1"}],
            "qasper_candidate_generation": generator,
            "qasper_canonical_semantic_pack": {
                "contract_id": QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
                "semantic_pack_digest": _PACK_DIGEST,
                "span_universe_digest": qasper_canonical_span_universe_digest(
                    _canonical_pack_records()
                ),
                "candidate_transaction_id": _PACK_TRANSACTION_ID,
                "records": _canonical_pack_records(),
                "slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "evidence_refs": ["E1:S1"],
                    }
                ],
                "proposition_binding": deepcopy(
                    generator["candidate_evidence_set_binding"]
                ),
                "source_packing_observation": deepcopy(source_packing),
            },
        },
        "controller_trace": [_recovery_transition()],
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_status": "answered",
        "terminal_outcome": "answered",
        "terminal_semantic_commit": debug_row["terminal_semantic_commit"],
        "answer_finalization": {"status": "accepted", "answer": "yes"},
        "qasper_annotation_scores": [{"gold": "yes", "f1": 1.0}],
        "qasper_annotation_diagnostics": {"ambiguous": False},
        "metrics": {"qasper_f1": 1.0, "native_score": 1.0},
    }
    return attach_valid_terminal_projection(prediction)


def _canonical_pack_records() -> list[dict]:
    return [
        {
            "evidence_id": "evidence-1",
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "The authors compared systems.",
                    "span_start": 0,
                    "span_end": 29,
                    "event_id": "event-1",
                    "allowed_proposition_slots": [
                        "actor",
                        "predicate",
                        "object",
                    ],
                }
            ],
        }
    ]


def _recovery_transition() -> dict:
    return {
        "stage": "evidence_rebind",
        "semantic_pack_digest_before": "c" * 64,
        "semantic_pack_digest_after": "c" * 64,
        "semantic_pack_digest_changed": False,
        "slot_state_digest_before": "d" * 64,
        "slot_state_digest_after": "d" * 64,
        "slot_state_digest_changed": False,
        "proposition_binding_digest_before": "e" * 64,
        "proposition_binding_digest_after": "e" * 64,
        "proposition_binding_digest_changed": False,
    }


def _run_context() -> dict:
    return {
        "worktree_path": "/workspace/MARA",
        "run_provenance": {
            "git": {"commit": _CODE_SHA, "dirty": False},
            "manifest": {"path": "/runs/manifest.json", "sha256": _MANIFEST_SHA},
            "config": {"engine": "legacy_text_rag", "route": "all"},
            "contract_hash": "f" * 64,
            "execution_hash": "1" * 64,
            "service": {
                "contract": "2" * 64,
                "retrieval_endpoint": "http://retrieval",
                "text_llm_endpoint": "http://provider/v1",
            },
        },
        "backend_metadata": {
            "text_rag": {
                "generator_backend": "candidate-model:v1",
                "text_retriever": "retriever:v1",
            }
        },
    }


def _transaction() -> dict:
    prediction, debug_row = _prediction_and_debug_row()
    return qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
        origin="online",
    )


def test_transaction_records_all_twelve_evidence_blocks_with_a_digest_chain() -> None:
    transaction = _transaction()

    assert transaction["contract_id"] == "qasper_causal_transaction.v1"
    assert transaction["status"] == "complete"
    assert transaction["incompleteness_reasons"] == []
    assert [stage["stage"] for stage in transaction["stages"]] == list(
        QASPER_CAUSAL_TRANSACTION_STAGES
    )
    assert [stage["stage_index"] for stage in transaction["stages"]] == list(
        range(1, 13)
    )
    assert all(len(stage["payload_digest"]) == 64 for stage in transaction["stages"])
    assert all(len(stage["chain_digest"]) == 64 for stage in transaction["stages"])
    assert len(transaction["transaction_digest"]) == 64


def test_transaction_keeps_exact_raw_responses_and_model_inputs() -> None:
    transaction = _transaction()
    stages = {stage["stage"]: stage for stage in transaction["stages"]}

    model = stages["model_response_and_parser"]["payload"]
    verifier = stages["verifier_and_auditor"]["payload"]
    assert model["candidate_generation"]["raw_response"] == '{"candidate":"yes"}'
    assert verifier["proposal_input"]["prompt"] == "candidate-bound verifier prompt"
    assert verifier["audit_input"]["prompt"] == "independent auditor prompt"
    assert (
        verifier["proposal_output"]["attempts"][0]["parsed_value"][
            "canonical_evidence_plan_id"
        ]
        == "6" * 64
    )


def test_candidate_input_stage_freezes_request_identity_counts_and_budget() -> None:
    transaction = _transaction()
    candidate = transaction["stages"][2]["payload"]

    assert candidate["token_measurement"] == {
        "estimated_input_tokens": 30,
        "message_tokens": 20,
        "schema_tokens": 10,
        "tokenizer_identity": "fixture-tokenizer:v1",
        "tokenizer_method": "fixture_exact",
        "tokenizer_exact": True,
        "tokenizer_endpoint": "fixture://tokenizer",
        "tokenizer_failed": False,
        "tokenizer_failure_reason": "",
    }
    assert candidate["token_budget"] == {
        "candidate_input_token_budget": 3920,
        "max_model_len": 4096,
        "max_output_tokens": 48,
        "token_headroom_tokens": 128,
    }
    assert candidate["selected_record_ids"] == ["evidence-1"]
    assert candidate["selected_record_ids_digest"] == canonical_digest(["evidence-1"])
    assert candidate["candidate_request_drop_count"] == 0
    assert candidate["request_drop_count"] == 0


def test_transaction_fails_closed_when_an_exact_model_response_was_truncated() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    debug_row["main_candidate_generator"]["raw_response_truncated"] = True

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
        origin="online",
    )

    assert transaction["status"] == "incomplete"
    assert "model_response_and_parser:candidate_raw_response_truncated" in (
        transaction["incompleteness_reasons"]
    )


def test_first_divergence_stops_comparison_and_suppresses_later_diagnostics() -> None:
    reference_prediction, reference_row = _prediction_and_debug_row()
    replay_prediction = deepcopy(reference_prediction)
    replay_row = deepcopy(reference_row)
    replay_prediction["retrieved_hits"][0]["text"] = "different retrieval"
    replay_prediction["answer_for_scoring"] = "no"
    reference = qasper_causal_transaction(
        reference_prediction,
        reference_row,
        run_context=_run_context(),
        origin="online",
    )
    replay = qasper_causal_transaction(
        replay_prediction,
        replay_row,
        run_context=_run_context(),
        origin="local_replay",
    )

    comparison = compare_qasper_causal_transactions(reference, replay)

    assert comparison["status"] == "diverged"
    assert comparison["first_divergence"]["stage_index"] == 2
    assert comparison["first_divergence"]["stage"] == "retrieval_and_ranking"
    assert comparison["investigation_stage"] == "retrieval_and_ranking"
    assert comparison["later_stages_evaluated"] is False
    assert "later_divergences" not in comparison


def test_candidate_request_truncation_does_not_change_retrieval_ranking_stage() -> None:
    reference_prediction, reference_row = _prediction_and_debug_row()
    replay_prediction = deepcopy(reference_prediction)
    replay_row = deepcopy(reference_row)
    replay_prediction["evidence_metadata"]["candidate_ranked_evidence"] = []
    reference = qasper_causal_transaction(
        reference_prediction,
        reference_row,
        run_context=_run_context(),
        origin="online",
    )
    replay = qasper_causal_transaction(
        replay_prediction,
        replay_row,
        run_context=_run_context(),
        origin="local_replay",
    )

    comparison = compare_qasper_causal_transaction_prefix(
        reference,
        replay,
        through_stage=2,
    )

    assert comparison["status"] == "matched_prefix"
    retrieval = reference["stages"][1]["payload"]
    assert retrieval["ranking_source"] == "retrieved_hits_order"


def test_tampered_stage_digest_is_the_only_reported_investigation_boundary() -> None:
    reference = _transaction()
    replay = deepcopy(reference)
    replay["origin"] = "local_replay"
    replay["stages"][3]["payload_digest"] = "0" * 64

    comparison = compare_qasper_causal_transactions(reference, replay)

    assert comparison["status"] == "invalid"
    assert comparison["first_divergence"] == {
        "stage_index": 4,
        "stage": "proposition_spans_and_selector_universe",
        "reason": "replay_stage_integrity_invalid",
    }
    assert comparison["later_stages_evaluated"] is False


def test_prefix_comparison_does_not_inspect_declared_non_replayed_stages() -> None:
    reference_prediction, reference_row = _prediction_and_debug_row()
    replay_prediction, replay_row = _prediction_and_debug_row()
    replay_row["main_candidate_generator"]["raw_response_truncated"] = True
    reference = qasper_causal_transaction(
        reference_prediction,
        reference_row,
        run_context=_run_context(),
        origin="online",
    )
    replay = qasper_causal_transaction(
        replay_prediction,
        replay_row,
        run_context=_run_context(),
        origin="local_replay",
    )

    comparison = compare_qasper_causal_transaction_prefix(
        reference,
        replay,
        through_stage=7,
    )

    assert comparison["status"] == "matched_prefix"
    assert comparison["compared_stage_count"] == 7
    assert comparison["comparison_scope"]["through_stage"] == (
        "projected_plan_authority"
    )
    assert comparison["later_stages_evaluated"] is False


def test_earlier_digest_difference_masks_later_integrity_damage() -> None:
    reference_prediction, reference_row = _prediction_and_debug_row()
    replay_prediction = deepcopy(reference_prediction)
    replay_row = deepcopy(reference_row)
    replay_prediction["retrieved_hits"][0]["text"] = "different retrieval"
    reference = qasper_causal_transaction(
        reference_prediction,
        reference_row,
        run_context=_run_context(),
    )
    replay = qasper_causal_transaction(
        replay_prediction,
        replay_row,
        run_context=_run_context(),
        origin="local_replay",
    )
    replay["stages"][9]["payload_digest"] = "0" * 64

    comparison = compare_qasper_causal_transactions(reference, replay)

    assert comparison["status"] == "diverged"
    assert comparison["first_divergence"]["stage_index"] == 2
    assert comparison["later_stages_evaluated"] is False
