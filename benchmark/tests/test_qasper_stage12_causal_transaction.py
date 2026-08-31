from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import _run_context
from benchmark.tests.test_qasper_stage11_causal_transaction import (
    _terminal_projection_fixture,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    _local_replay_prediction,
    natural_causal_transaction_replay,
)


def _stage_twelve_replay_context(prediction: dict) -> dict:
    metadata = prediction["evidence_metadata"]
    reference = qasper_causal_transaction(
        prediction,
        {
            "main_candidate_generator": metadata["qasper_candidate_generation"],
            "semantic_verifier": metadata["semantic_proposition_verifier"],
        },
        run_context=_run_context(),
    )
    payload = reference["stages"][11]["payload"]
    run_context = deepcopy(_run_context())
    run_context["causal_replay_provenance"] = {
        "contract_id": "qasper_causal_replay_provenance.v1",
        "source_prediction_digest": canonical_digest(prediction),
        "provider_model_identity": deepcopy(
            payload["run_provenance"]["provider_model_identity"]
        ),
        "provider_model_identity_digest": payload["run_provenance"][
            "provider_model_identity_digest"
        ],
    }
    return run_context


def test_stage_twelve_replays_frozen_provenance_and_artifact_binding() -> None:
    prediction, context = _terminal_projection_fixture()
    replay_context = _stage_twelve_replay_context(prediction)

    replay = natural_causal_transaction_replay(
        prediction,
        context,
        through_stage=12,
        run_context=replay_context,
    )  # type: ignore[call-arg]

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 12
    assert replay["through_stage"] == "run_provenance_and_artifact"
    assert replay["comparison"]["status"] == "matched_prefix"
    reference = replay["reference_transaction"]["stages"][11]
    local = replay["local_replay_transaction"]["stages"][11]
    assert local["status"] == "complete"
    assert local["comparison_digest"] == reference["comparison_digest"]


def test_stage_twelve_does_not_hash_the_mutated_local_replay_as_source() -> None:
    prediction, context = _terminal_projection_fixture()
    replay_context = _stage_twelve_replay_context(prediction)
    source_digest = replay_context["causal_replay_provenance"][
        "source_prediction_digest"
    ]

    local_prediction = _local_replay_prediction(prediction, context)
    assert canonical_digest(local_prediction) != source_digest

    replay = natural_causal_transaction_replay(
        prediction,
        context,
        through_stage=12,
        run_context=replay_context,
    )  # type: ignore[call-arg]
    local_artifact = replay["local_replay_transaction"]["stages"][11]["payload"][
        "artifact_binding"
    ]

    assert local_artifact["source_prediction_digest"] == source_digest


def test_stage_twelve_fails_closed_on_tampered_frozen_provider_identity() -> None:
    prediction, context = _terminal_projection_fixture()
    replay_context = _stage_twelve_replay_context(prediction)
    replay_context["causal_replay_provenance"]["provider_model_identity_digest"] = (
        "0" * 64
    )

    replay = natural_causal_transaction_replay(
        prediction,
        context,
        through_stage=12,
        run_context=replay_context,
    )  # type: ignore[call-arg]

    stage = replay["local_replay_transaction"]["stages"][11]
    assert stage["status"] == "incomplete"
    assert stage["incompleteness_reasons"] == [
        "causal_replay_provider_model_identity_digest_mismatch"
    ]
