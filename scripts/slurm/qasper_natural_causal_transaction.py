from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transaction_prefix,
)
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows

_REPLAY_THROUGH_STAGE = 8


def natural_causal_transaction_replay(
    row: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    reference = _causal_transaction(row, origin="online_reference")
    replay_prediction = _local_replay_prediction(row, context)
    replay = _causal_transaction(replay_prediction, origin="local_replay")
    comparison = compare_qasper_causal_transaction_prefix(
        reference,
        replay,
        through_stage=_REPLAY_THROUGH_STAGE,
    )
    return {
        "contract_id": "qasper_natural_causal_transaction_replay.v1",
        "status": (
            "matched" if comparison.get("status") == "matched_prefix" else "failed"
        ),
        "comparison_scope": "causal_replay_through_model_response_and_parser",
        "through_stage_index": _REPLAY_THROUGH_STAGE,
        "through_stage": QASPER_CAUSAL_TRANSACTION_STAGES[_REPLAY_THROUGH_STAGE - 1],
        "hard_rule": "stop_at_first_divergence",
        "reference_transaction": reference,
        "local_replay_transaction": replay,
        "comparison": comparison,
    }


def _causal_transaction(
    prediction: dict[str, Any],
    *,
    origin: str,
) -> dict[str, Any]:
    rows = qasper_semantic_debug_rows([prediction], include_missing=True)
    if not rows:
        return {}
    transaction = deepcopy(rows[0].get("causal_transaction") or {})
    transaction["origin"] = origin
    digest_payload = {
        key: value for key, value in transaction.items() if key != "transaction_digest"
    }
    transaction["transaction_digest"] = canonical_digest(digest_payload)
    return transaction


def _local_replay_prediction(
    row: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    prediction = deepcopy(row)
    metadata = _terminal_metadata(prediction)
    local_pack = deepcopy(
        _mapping(context.bundle.metadata).get("qasper_canonical_semantic_pack") or {}
    )
    source = deepcopy(_mapping(local_pack.get("source_packing_observation")))
    plan_construction = deepcopy(
        _mapping(context.binding).get("plan_construction_trace") or {}
    )
    metadata.update(
        {
            "candidate_ranked_evidence": deepcopy(
                _mapping(context.bundle.metadata).get("candidate_ranked_evidence") or []
            ),
            "qasper_canonical_semantic_pack": local_pack,
            "qasper_candidate_generation": deepcopy(context.candidate_generation),
            "semantic_proposition_verifier": {
                "contract_id": "semantic_proposition_verifier_runtime.v3",
                "status": "not_run_after_candidate_response_replay",
                "reason": "stage_nine_not_replayed",
                "candidate_verification_status": "not_started_in_replay",
                "proposal_status": "not_started",
                "audit_status": "not_started",
                "semantic_data_lineage": {
                    "contract_id": "semantic_proposition_data_lineage.v1",
                    "source_packing": source,
                    "plan_construction": plan_construction,
                },
            },
        }
    )
    _replace_terminal_metadata(prediction, metadata)
    return prediction


def _replace_terminal_metadata(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    prediction["evidence_metadata"] = deepcopy(metadata)
    terminal = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    if terminal:
        terminal["metadata"] = deepcopy(metadata)
        prediction["engine_terminal_evidence_bundle"] = terminal


def _terminal_metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    terminal = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    return deepcopy(
        _mapping(terminal.get("metadata"))
        or _mapping(prediction.get("evidence_metadata"))
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
