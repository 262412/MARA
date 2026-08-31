from __future__ import annotations

import json
from pathlib import Path

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import _run_context
from benchmark.tests.test_qasper_stage11_causal_transaction import (
    _terminal_projection_fixture,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    _local_replay_prediction,
    causal_replay_run_context,
    natural_causal_transaction_replay,
)
from scripts.slurm.qasper_natural_semantic_pack_probe import load_probe_run_contexts


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
    return causal_replay_run_context(prediction, reference)


def test_stage_twelve_replays_frozen_provenance_and_artifact_binding() -> None:
    prediction, context = _terminal_projection_fixture()
    replay_context = _stage_twelve_replay_context(prediction)

    replay = natural_causal_transaction_replay(
        prediction,
        context,
        through_stage=12,
        run_context=replay_context,
    )

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 12
    assert replay["through_stage"] == "run_provenance_and_artifact"
    assert replay["comparison"]["status"] == "matched"
    assert replay["comparison"]["later_stages_evaluated"] is True
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
    )
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
    )

    stage = replay["local_replay_transaction"]["stages"][11]
    assert stage["status"] == "incomplete"
    assert stage["incompleteness_reasons"] == [
        "causal_replay_provider_model_identity_digest_mismatch"
    ]


def test_stage_twelve_rejects_a_source_prediction_changed_after_freeze() -> None:
    prediction, _context = _terminal_projection_fixture()
    replay_context = _stage_twelve_replay_context(prediction)
    prediction["question"] = "A different question after the source artifact froze"

    try:
        causal_replay_run_context(
            prediction,
            qasper_causal_transaction(
                prediction,
                {
                    "main_candidate_generator": prediction["evidence_metadata"][
                        "qasper_candidate_generation"
                    ],
                    "semantic_verifier": prediction["evidence_metadata"][
                        "semantic_proposition_verifier"
                    ],
                },
                run_context=replay_context,
            ),
        )
    except ValueError as exc:
        assert str(exc) == "stage_twelve_source_prediction_digest_mismatch"
    else:
        raise AssertionError("mutated source prediction must fail closed")


def test_stage_twelve_loader_joins_the_frozen_trace_by_sample_and_route(
    tmp_path: Path,
) -> None:
    prediction, _context = _terminal_projection_fixture()
    metadata = prediction["evidence_metadata"]
    transaction = qasper_causal_transaction(
        prediction,
        {
            "main_candidate_generator": metadata["qasper_candidate_generation"],
            "semantic_verifier": metadata["semantic_proposition_verifier"],
        },
        run_context=_run_context(),
    )
    predictions_path = tmp_path / "predictions.jsonl"
    traces_path = tmp_path / "semantic_debug_traces.jsonl"
    predictions_path.write_text(json.dumps(prediction) + "\n", encoding="utf-8")
    traces_path.write_text(
        json.dumps(
            {
                "example_id": prediction["example_id"],
                "route": prediction["route"],
                "causal_transaction": transaction,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    contexts = load_probe_run_contexts(predictions_path, [prediction])

    key = (str(prediction["example_id"]), str(prediction["route"]))
    assert contexts[key]["causal_replay_provenance"] == (
        _stage_twelve_replay_context(prediction)["causal_replay_provenance"]
    )
