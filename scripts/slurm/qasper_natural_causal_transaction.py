from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    qasper_canonical_span_universe_digest,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256
from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transaction_prefix,
    compare_qasper_causal_transactions,
)
from benchmark.qasper_causal_transaction_stages import stage_comparison_payload
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows
from scripts.slurm.qasper_natural_semantic_response_replay import (
    replay_frozen_semantic_verifier,
)

_REPLAY_THROUGH_STAGE = 12


def causal_replay_run_context(
    prediction: Mapping[str, Any],
    reference_transaction: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and project the frozen online Stage 12 input for local replay."""

    payload = _stage_twelve_payload(prediction, reference_transaction)
    (
        provenance,
        code,
        manifest,
        config,
        provider,
        source_digest,
    ) = _stage_twelve_provenance_values(prediction, payload)
    service = deepcopy(_mapping(provider.get("service")))
    route_backend = deepcopy(_mapping(provider.get("route_backend")))
    route = str(prediction.get("route") or "")
    provider_digest = canonical_digest(provider)
    return {
        "worktree_path": str(code["worktree_path"]),
        "run_provenance": {
            "git": {"commit": str(code["sha"]), "dirty": False},
            "manifest": manifest,
            "config": config,
            "contract_hash": str(provenance.get("contract_hash") or ""),
            "execution_hash": str(provenance.get("execution_hash") or ""),
            "service": service,
        },
        "backend_metadata": {route: route_backend},
        "causal_replay_provenance": {
            "contract_id": "qasper_causal_replay_provenance.v1",
            "source_prediction_digest": source_digest,
            "provider_model_identity": provider,
            "provider_model_identity_digest": provider_digest,
        },
    }


def _stage_twelve_payload(
    prediction: Mapping[str, Any],
    reference_transaction: Mapping[str, Any],
) -> dict[str, Any]:
    key = _mapping(reference_transaction.get("transaction_key"))
    if key != {
        "example_id": str(prediction.get("example_id") or ""),
        "route": str(prediction.get("route") or ""),
    }:
        raise ValueError("stage_twelve_transaction_key_mismatch")
    stages = reference_transaction.get("stages")
    if not isinstance(stages, list) or len(stages) < 12:
        raise ValueError("stage_twelve_reference_missing")
    stage = _mapping(stages[11])
    if stage.get("stage_index") != 12 or stage.get("stage") != (
        "run_provenance_and_artifact"
    ):
        raise ValueError("stage_twelve_reference_invalid")
    payload = _mapping(stage.get("payload"))
    if stage.get("status") != "complete" or payload.get("status") != "complete":
        raise ValueError("stage_twelve_reference_incomplete")
    if canonical_digest(payload) != stage.get("payload_digest"):
        raise ValueError("stage_twelve_payload_digest_mismatch")
    comparison = stage_comparison_payload("run_provenance_and_artifact", payload)
    if canonical_digest(comparison) != stage.get("comparison_digest"):
        raise ValueError("stage_twelve_comparison_digest_mismatch")
    chain_payload = {
        "stage_index": 12,
        "stage": "run_provenance_and_artifact",
        "payload_digest": stage.get("payload_digest"),
        "previous_chain_digest": stage.get("previous_chain_digest"),
    }
    if canonical_digest(chain_payload) != stage.get("chain_digest"):
        raise ValueError("stage_twelve_chain_digest_mismatch")
    return payload


def _stage_twelve_provenance_values(
    prediction: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    str,
]:
    provenance = _mapping(payload.get("run_provenance"))
    code = _mapping(provenance.get("code_identity"))
    manifest = deepcopy(_mapping(provenance.get("manifest")))
    config = deepcopy(_mapping(provenance.get("config")))
    provider = deepcopy(_mapping(provenance.get("provider_model_identity")))
    artifact = deepcopy(_mapping(payload.get("artifact_binding")))
    source_digest = str(artifact.get("source_prediction_digest") or "")
    if source_digest != canonical_digest(prediction):
        raise ValueError("stage_twelve_source_prediction_digest_mismatch")
    if canonical_digest(artifact) != payload.get("artifact_binding_digest"):
        raise ValueError("stage_twelve_artifact_binding_digest_mismatch")
    if canonical_digest(config) != provenance.get("config_digest"):
        raise ValueError("stage_twelve_config_digest_mismatch")
    provider_digest = canonical_digest(provider)
    if provider_digest != provenance.get("provider_model_identity_digest"):
        raise ValueError("stage_twelve_provider_model_identity_digest_mismatch")
    if not _git_sha(code.get("sha")):
        raise ValueError("stage_twelve_code_sha_missing")
    if not str(code.get("worktree_path") or ""):
        raise ValueError("stage_twelve_worktree_path_missing")
    if code.get("worktree_clean") is not True:
        raise ValueError("stage_twelve_worktree_not_clean")
    if not _sha256(manifest.get("sha256")):
        raise ValueError("stage_twelve_manifest_digest_missing")
    if not config:
        raise ValueError("stage_twelve_config_missing")
    if not any(
        provider.get(name)
        for name in ("candidate_model", "verifier_model", "auditor_model")
    ):
        raise ValueError("stage_twelve_provider_model_identity_missing")
    return provenance, code, manifest, config, provider, source_digest


def natural_causal_transaction_replay(
    row: dict[str, Any],
    context: Any,
    *,
    through_stage: int = _REPLAY_THROUGH_STAGE,
    run_context: Mapping[str, Any] | None = None,
    preserve_frozen_semantic_projection: bool = False,
) -> dict[str, Any]:
    reference = _causal_transaction(
        row,
        origin="online_reference",
        run_context=run_context,
    )
    replay_prediction = _local_replay_prediction(
        row,
        context,
        preserve_frozen_semantic_projection=preserve_frozen_semantic_projection,
    )
    replay = _causal_transaction(
        replay_prediction,
        origin="local_replay",
        run_context=run_context,
    )
    comparison = (
        compare_qasper_causal_transactions(reference, replay)
        if through_stage == len(QASPER_CAUSAL_TRANSACTION_STAGES)
        else compare_qasper_causal_transaction_prefix(
            reference,
            replay,
            through_stage=through_stage,
        )
    )
    return {
        "contract_id": "qasper_natural_causal_transaction_replay.v1",
        "status": (
            "matched"
            if comparison.get("status") in {"matched", "matched_prefix"}
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
        "local_replay_transaction": replay,
        "comparison": comparison,
    }


def _causal_transaction(
    prediction: dict[str, Any],
    *,
    origin: str,
    run_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = qasper_semantic_debug_rows(
        [prediction],
        include_missing=True,
        run_context=run_context,
    )
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
    *,
    preserve_frozen_semantic_projection: bool = False,
) -> dict[str, Any]:
    if preserve_frozen_semantic_projection:
        return _local_frozen_replay_prediction(row, context)
    return _local_current_replay_prediction(row, context)


def _local_current_replay_prediction(
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
    local_lineage = {
        "contract_id": "semantic_proposition_data_lineage.v1",
        "source_packing": source,
        "plan_construction": plan_construction,
    }
    verifier = replay_frozen_semantic_verifier(
        _mapping(metadata.get("semantic_proposition_verifier")),
        question=str(prediction.get("question") or ""),
        bundle=context.bundle,
        slots=list(context.slots),
        binding=context.binding,
        candidate_generation=context.candidate_generation,
        local_lineage=local_lineage,
    )
    metadata.update(
        {
            "candidate_ranked_evidence": deepcopy(
                _mapping(context.bundle.metadata).get("candidate_ranked_evidence") or []
            ),
            "qasper_canonical_semantic_pack": local_pack,
            "qasper_candidate_generation": deepcopy(context.candidate_generation),
            "semantic_proposition_verifier": verifier,
        }
    )
    _replace_terminal_metadata(prediction, metadata)
    return prediction


def _local_frozen_replay_prediction(
    row: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    prediction = deepcopy(row)
    terminal_metadata = _terminal_metadata(prediction)
    candidate_metadata = deepcopy(_mapping(prediction.get("evidence_metadata")))
    frozen_pack, frozen_candidate = _validated_frozen_candidate_stage(
        candidate_metadata,
        question=str(prediction.get("question") or ""),
    )
    source = deepcopy(_mapping(frozen_pack.get("source_packing_observation")))
    frozen_binding = deepcopy(_mapping(frozen_pack.get("proposition_binding")))
    plan_construction = deepcopy(
        _mapping(frozen_binding).get("plan_construction_trace") or {}
    )
    local_lineage = {
        "contract_id": "semantic_proposition_data_lineage.v1",
        "source_packing": source,
        "plan_construction": plan_construction,
    }
    bundle_value = _mapping(prediction.get("evidence_bundle"))
    frozen_bundle = EvidenceBundle(
        route=str(bundle_value.get("route") or prediction.get("route") or ""),
        items=deepcopy(list(bundle_value.get("items") or [])),
        metadata={"qasper_canonical_semantic_pack": deepcopy(frozen_pack)},
    )
    verifier = replay_frozen_semantic_verifier(
        _mapping(terminal_metadata.get("semantic_proposition_verifier")),
        question=str(prediction.get("question") or ""),
        bundle=frozen_bundle,
        slots=deepcopy(list(frozen_pack.get("slots") or [])),
        binding=frozen_binding,
        candidate_generation=frozen_candidate,
        local_lineage=local_lineage,
        preserve_frozen_projection=True,
    )
    metadata = candidate_metadata
    metadata.update(
        {
            "qasper_canonical_semantic_pack": frozen_pack,
            "qasper_candidate_generation": frozen_candidate,
            "semantic_proposition_verifier": verifier,
        }
    )
    _replace_terminal_metadata(prediction, metadata)
    return prediction


def _validated_frozen_candidate_stage(
    metadata: Mapping[str, Any],
    *,
    question: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pack = deepcopy(_mapping(metadata.get("qasper_canonical_semantic_pack")))
    candidate = deepcopy(_mapping(metadata.get("qasper_candidate_generation")))
    identity_digest = str(pack.pop("pack_identity_digest", "") or "")
    if (
        pack.get("contract_id") != QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT
        or not is_sha256(identity_digest)
        or canonical_digest(pack) != identity_digest
        or pack.get("question_digest") != canonical_digest(question.strip())
    ):
        raise ValueError("frozen candidate semantic pack identity mismatch")
    pack["pack_identity_digest"] = identity_digest
    records = pack.get("records")
    slots = pack.get("slots")
    binding = pack.get("proposition_binding")
    if (
        not isinstance(records, list)
        or not isinstance(slots, list)
        or not isinstance(binding, Mapping)
        or qasper_canonical_span_universe_digest(records)
        != pack.get("span_universe_digest")
    ):
        raise ValueError("frozen candidate semantic pack structure mismatch")
    transaction_id = str(candidate.get("transaction_id") or "")
    if (
        not transaction_id
        or pack.get("candidate_transaction_id") != transaction_id
        or candidate.get("canonical_semantic_pack_contract_id")
        != pack.get("contract_id")
        or candidate.get("canonical_semantic_pack_digest")
        != pack.get("semantic_pack_digest")
        or candidate.get("canonical_span_universe_digest")
        != pack.get("span_universe_digest")
        or candidate.get("canonical_pack_candidate_transaction_id") != transaction_id
    ):
        raise ValueError("frozen candidate semantic pack continuity mismatch")
    return pack, candidate


def _replace_terminal_metadata(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    prediction["evidence_metadata"] = deepcopy(metadata)
    prediction["_qasper_causal_replay_metadata"] = deepcopy(metadata)


def _terminal_metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    terminal = _mapping(prediction.get("engine_terminal_evidence_bundle"))
    return deepcopy(
        _mapping(terminal.get("metadata"))
        or _mapping(prediction.get("evidence_metadata"))
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _git_sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(
        character in "0123456789abcdef" for character in text
    )


def _sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )
