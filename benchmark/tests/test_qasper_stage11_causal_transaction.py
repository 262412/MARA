from __future__ import annotations

from copy import deepcopy

from ktem.docqa.engine_terminal_projection import engine_terminal_projection
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_models import GuardrailDecision
from ktem.docqa.verification import VerifyDecision

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.qasper_runtime_projection import runtime_projection_present
from benchmark.tests.test_qasper_causal_transaction import _run_context
from benchmark.tests.test_qasper_stage9_causal_transaction import (
    _current_semantic_io_fixture,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    _local_replay_prediction,
    natural_causal_transaction_replay,
)


def _terminal_projection_fixture() -> tuple[dict, object]:
    prediction, context = _current_semantic_io_fixture()
    bundle = EvidenceBundle(
        route="text_rag",
        items=deepcopy(prediction["evidence_bundle"]["items"]),
        metadata=deepcopy(prediction["evidence_metadata"]),
    )
    verify = VerifyDecision(
        mode="strict",
        status="verified",
        reason="",
        action="generate",
        canonical_answer_polarity="yes",
    )
    guardrail = GuardrailDecision(status="ok", action="return", reason="")
    (
        answer,
        state,
        terminal_verify,
        terminal_guardrail,
        terminal_bundle,
        projection_hash,
    ) = engine_terminal_projection("yes", verify, guardrail, bundle)
    commit = state["terminal_semantic_commit"]
    prediction.update(
        predicted_answer=answer,
        answer_for_scoring=answer,
        answer_status=commit["answer_status"],
        terminal_outcome=commit["outcome"],
        engine_terminal_answer=answer,
        engine_terminal_state=state,
        engine_verify_decision=terminal_verify,
        engine_terminal_guardrail_decision=terminal_guardrail,
        engine_terminal_evidence_bundle=terminal_bundle,
        engine_terminal_projection_hash=projection_hash,
        engine_terminal_commit=commit,
        terminal_semantic_commit=commit,
    )
    return prediction, context


def test_stage_eleven_preserves_the_frozen_terminal_projection_during_replay() -> None:
    prediction, context = _terminal_projection_fixture()

    local = _local_replay_prediction(prediction, context)

    assert runtime_projection_present(prediction) is True
    assert runtime_projection_present(local) is True
    assert local["engine_terminal_evidence_bundle"] == (
        prediction["engine_terminal_evidence_bundle"]
    )
    assert local["engine_terminal_projection_hash"] == (
        prediction["engine_terminal_projection_hash"]
    )


def test_stage_eleven_replays_finalizer_and_scorer_input() -> None:
    prediction, context = _terminal_projection_fixture()

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 11
    reference = replay["reference_transaction"]["stages"][10]
    local = replay["local_replay_transaction"]["stages"][10]
    assert reference["status"] == "complete"
    assert local["status"] == "complete"
    assert local["comparison_digest"] == reference["comparison_digest"]


def test_stage_eleven_rejects_a_scoring_answer_outside_the_terminal_commit() -> None:
    prediction, _context = _terminal_projection_fixture()
    prediction["answer_for_scoring"] = "no"
    debug_row = {
        "main_candidate_generator": prediction["evidence_metadata"][
            "qasper_candidate_generation"
        ],
        "semantic_verifier": prediction["evidence_metadata"][
            "semantic_proposition_verifier"
        ],
    }

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][10]

    assert stage["status"] == "incomplete"
    assert stage["incompleteness_reasons"] == [
        "scorer_input_terminal_answer_mismatch"
    ]
