from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256
from benchmark.qasper_causal_transaction_stages import (
    causal_transaction_stage_payloads,
    stage_comparison_payload,
)

QASPER_CAUSAL_TRANSACTION_STAGES = (
    "dataset_and_gold",
    "retrieval_and_ranking",
    "candidate_input",
    "proposition_spans_and_selector_universe",
    "candidate_plans",
    "selected_local_plan",
    "projected_plan_authority",
    "model_response_and_parser",
    "verifier_and_auditor",
    "recovery_state",
    "finalizer_and_scorer",
    "run_provenance_and_artifact",
)


def qasper_causal_transaction(
    prediction: Mapping[str, Any],
    debug_row: Mapping[str, Any],
    *,
    run_context: Mapping[str, Any] | None = None,
    origin: str = "online",
) -> dict[str, Any]:
    """Freeze one sample-route execution as a digest-linked causal transaction."""

    payloads = causal_transaction_stage_payloads(
        prediction,
        debug_row,
        run_context or {},
    )
    stages: list[dict[str, Any]] = []
    previous_chain_digest = ""
    reasons: list[str] = []
    for index, name in enumerate(QASPER_CAUSAL_TRANSACTION_STAGES, start=1):
        payload = deepcopy(payloads.get(name) or {})
        stage = _stage_record(
            index,
            name,
            payload,
            previous_chain_digest=previous_chain_digest,
        )
        stages.append(stage)
        previous_chain_digest = stage["chain_digest"]
        reasons.extend(
            f"{name}:{reason}" for reason in payload.get("incompleteness_reasons") or []
        )
    transaction = {
        "contract_id": "qasper_causal_transaction.v1",
        "origin": str(origin or ""),
        "transaction_key": {
            "example_id": str(prediction.get("example_id") or ""),
            "route": str(prediction.get("route") or ""),
        },
        "status": "complete" if not reasons else "incomplete",
        "incompleteness_reasons": list(dict.fromkeys(reasons)),
        "stage_count": len(stages),
        "stage_order": list(QASPER_CAUSAL_TRANSACTION_STAGES),
        "stages": stages,
        "terminal_chain_digest": previous_chain_digest,
    }
    transaction["transaction_digest"] = canonical_digest(transaction)
    return transaction


def compare_qasper_causal_transactions(
    reference: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare in order and stop permanently at the first causal divergence."""

    stage_count = len(QASPER_CAUSAL_TRANSACTION_STAGES)
    invalid = _comparison_header_failure(reference, replay)
    if invalid is not None:
        return _comparison_result("invalid", invalid, compared_stage_count=0)
    failure, reference_previous, replay_previous = _compare_stage_prefix(
        reference,
        replay,
        through_stage=stage_count,
    )
    if failure is not None:
        return failure
    for label, transaction, previous in (
        ("reference", reference, reference_previous),
        ("replay", replay, replay_previous),
    ):
        invalid = _transaction_tail_failure(
            transaction,
            label=label,
            terminal_chain_digest=previous,
        )
        if invalid is not None:
            return _comparison_result(
                "invalid",
                invalid,
                compared_stage_count=stage_count,
            )
    return {
        "contract_id": "qasper_causal_transaction_comparison.v1",
        "status": "matched",
        "transaction_key": deepcopy(reference.get("transaction_key") or {}),
        "compared_stage_count": stage_count,
        "first_divergence": {},
        "investigation_stage": "",
        "later_stages_evaluated": True,
        "hard_rule": "stop_at_first_divergence",
    }


def compare_qasper_causal_transaction_prefix(
    reference: Mapping[str, Any],
    replay: Mapping[str, Any],
    *,
    through_stage: int,
) -> dict[str, Any]:
    """Compare a declared deterministic prefix without inspecting later stages."""

    if not 1 <= through_stage <= len(QASPER_CAUSAL_TRANSACTION_STAGES):
        raise ValueError("through_stage_out_of_range")
    invalid = _comparison_header_failure(reference, replay)
    if invalid is not None:
        return _comparison_result("invalid", invalid, compared_stage_count=0)
    failure, _reference_previous, _replay_previous = _compare_stage_prefix(
        reference,
        replay,
        through_stage=through_stage,
    )
    if failure is not None:
        return failure
    return {
        "contract_id": "qasper_causal_transaction_comparison.v1",
        "status": "matched_prefix",
        "transaction_key": deepcopy(reference.get("transaction_key") or {}),
        "compared_stage_count": through_stage,
        "comparison_scope": {
            "through_stage_index": through_stage,
            "through_stage": QASPER_CAUSAL_TRANSACTION_STAGES[through_stage - 1],
        },
        "first_divergence": {},
        "investigation_stage": "",
        "later_stages_evaluated": False,
        "hard_rule": "stop_at_first_divergence",
    }


def _comparison_header_failure(
    reference: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> dict[str, Any] | None:
    if _mapping(reference.get("transaction_key")) != _mapping(
        replay.get("transaction_key")
    ):
        return {
            "stage_index": 0,
            "stage": "transaction_identity",
            "reason": "transaction_key_mismatch",
        }
    for label, transaction in (("reference", reference), ("replay", replay)):
        invalid = _transaction_header_failure(transaction, label=label)
        if invalid is not None:
            return invalid
    return None


def _compare_stage_prefix(
    reference: Mapping[str, Any],
    replay: Mapping[str, Any],
    *,
    through_stage: int,
) -> tuple[dict[str, Any] | None, str, str]:
    reference_previous = ""
    replay_previous = ""
    pairs = zip(_stage_list(reference), _stage_list(replay))
    for index, (expected, observed) in enumerate(pairs, start=1):
        if index > through_stage:
            break
        failure = _stage_pair_failure(
            index,
            expected,
            observed,
            reference_previous=reference_previous,
            replay_previous=replay_previous,
        )
        if failure is not None:
            return failure, reference_previous, replay_previous
        reference_previous = str(expected.get("chain_digest") or "")
        replay_previous = str(observed.get("chain_digest") or "")
    return None, reference_previous, replay_previous


def _stage_pair_failure(
    index: int,
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    reference_previous: str,
    replay_previous: str,
) -> dict[str, Any] | None:
    stage_name = str(expected.get("stage") or observed.get("stage") or "")
    for label, stage, previous in (
        ("reference", expected, reference_previous),
        ("replay", observed, replay_previous),
    ):
        reason = _stage_integrity_reason(
            stage,
            index=index,
            name=QASPER_CAUSAL_TRANSACTION_STAGES[index - 1],
            previous=previous,
        )
        if not reason and stage.get("status") != "complete":
            reason = "stage_incomplete"
        if reason:
            return _comparison_result(
                "invalid",
                _integrity_failure(
                    index,
                    stage_name,
                    f"{label}_{reason}",
                    payload=_mapping(stage.get("payload")),
                ),
                compared_stage_count=index - 1,
            )
    if expected.get("comparison_digest") == observed.get("comparison_digest"):
        return None
    divergence = {
        "stage_index": index,
        "stage": stage_name,
        "reason": "stage_comparison_digest_mismatch",
        "reference_digest": str(expected.get("comparison_digest") or ""),
        "replay_digest": str(observed.get("comparison_digest") or ""),
    }
    divergence.update(
        _digest_trace_fields(
            _mapping(expected.get("payload")) or _mapping(observed.get("payload"))
        )
    )
    return _comparison_result(
        "diverged",
        divergence,
        compared_stage_count=index - 1,
    )


def qasper_causal_transaction_complete(value: Mapping[str, Any]) -> bool:
    return bool(
        value.get("status") == "complete"
        and not value.get("incompleteness_reasons")
        and _first_integrity_failure(value, label="transaction") is None
    )


def qasper_causal_transaction_first_failure(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    return _first_integrity_failure(value, label="transaction") or {}


def _stage_record(
    index: int,
    name: str,
    payload: dict[str, Any],
    *,
    previous_chain_digest: str,
) -> dict[str, Any]:
    payload_digest = canonical_digest(payload)
    comparison_digest = canonical_digest(stage_comparison_payload(name, payload))
    chain_payload = {
        "stage_index": index,
        "stage": name,
        "payload_digest": payload_digest,
        "previous_chain_digest": previous_chain_digest,
    }
    return {
        "stage_index": index,
        "stage": name,
        "status": str(payload.get("status") or "incomplete"),
        "incompleteness_reasons": list(payload.get("incompleteness_reasons") or []),
        "payload": payload,
        "payload_digest": payload_digest,
        "comparison_digest": comparison_digest,
        "previous_chain_digest": previous_chain_digest,
        "chain_digest": canonical_digest(chain_payload),
    }


def _first_integrity_failure(
    transaction: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, Any] | None:
    header_failure = _transaction_header_failure(transaction, label=label)
    if header_failure is not None:
        return header_failure
    stages = _stage_list(transaction)
    previous = ""
    for index, (name, stage) in enumerate(
        zip(QASPER_CAUSAL_TRANSACTION_STAGES, stages),
        start=1,
    ):
        reason = _stage_integrity_reason(
            stage, index=index, name=name, previous=previous
        )
        if reason:
            return _integrity_failure(
                index,
                name,
                f"{label}_{reason}",
                payload=_mapping(stage.get("payload")),
            )
        if stage.get("status") != "complete":
            return _integrity_failure(
                index,
                name,
                f"{label}_stage_incomplete",
                payload=_mapping(stage.get("payload")),
            )
        previous = str(stage.get("chain_digest") or "")
    return _transaction_tail_failure(
        transaction,
        label=label,
        terminal_chain_digest=previous,
    )


def _transaction_header_failure(
    transaction: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, Any] | None:
    if transaction.get("contract_id") != "qasper_causal_transaction.v1":
        return _integrity_failure(
            0,
            "transaction_contract",
            f"{label}_contract_invalid",
        )
    if len(_stage_list(transaction)) != len(QASPER_CAUSAL_TRANSACTION_STAGES):
        return _integrity_failure(
            0,
            "transaction_contract",
            f"{label}_stage_count_invalid",
        )
    return None


def _transaction_tail_failure(
    transaction: Mapping[str, Any],
    *,
    label: str,
    terminal_chain_digest: str,
) -> dict[str, Any] | None:
    stage_count = len(QASPER_CAUSAL_TRANSACTION_STAGES)
    terminal_stage = QASPER_CAUSAL_TRANSACTION_STAGES[-1]
    if transaction.get("terminal_chain_digest") != terminal_chain_digest:
        return _integrity_failure(
            stage_count,
            terminal_stage,
            f"{label}_terminal_chain_digest_invalid",
        )
    payload = {
        key: value for key, value in transaction.items() if key != "transaction_digest"
    }
    if not is_sha256(transaction.get("transaction_digest")) or canonical_digest(
        payload
    ) != transaction.get("transaction_digest"):
        return _integrity_failure(
            stage_count,
            terminal_stage,
            f"{label}_transaction_digest_invalid",
        )
    if transaction.get("status") != "complete":
        return _integrity_failure(
            stage_count,
            terminal_stage,
            f"{label}_transaction_status_invalid",
        )
    return None


def _stage_integrity_reason(
    stage: Mapping[str, Any],
    *,
    index: int,
    name: str,
    previous: str,
) -> str:
    if stage.get("stage_index") != index or stage.get("stage") != name:
        return "stage_identity_invalid"
    payload = _mapping(stage.get("payload"))
    if canonical_digest(payload) != stage.get("payload_digest"):
        return "stage_integrity_invalid"
    if canonical_digest(stage_comparison_payload(name, payload)) != stage.get(
        "comparison_digest"
    ):
        return "stage_comparison_integrity_invalid"
    if stage.get("previous_chain_digest") != previous:
        return "stage_chain_predecessor_invalid"
    chain_payload = {
        "stage_index": index,
        "stage": name,
        "payload_digest": stage.get("payload_digest"),
        "previous_chain_digest": previous,
    }
    if canonical_digest(chain_payload) != stage.get("chain_digest"):
        return "stage_chain_digest_invalid"
    return ""


def _comparison_result(
    status: str,
    divergence: dict[str, Any],
    *,
    compared_stage_count: int,
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_causal_transaction_comparison.v1",
        "status": status,
        "compared_stage_count": compared_stage_count,
        "first_divergence": divergence,
        "investigation_stage": str(divergence.get("stage") or ""),
        "later_stages_evaluated": False,
        "hard_rule": "stop_at_first_divergence",
    }


def _integrity_failure(
    index: int,
    stage: str,
    reason: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    failure = {"stage_index": index, "stage": stage, "reason": reason}
    failure.update(_digest_trace_fields(payload or {}))
    return failure


def _digest_trace_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    """Carry canonical digest evidence into the first causal failure only."""

    candidates = [value]
    finalizer = value.get("finalizer_decision")
    if isinstance(finalizer, Mapping):
        candidates.append(finalizer)
    for key in (
        "canonical_projection_digest_trace",
        "canonical_digest_trace",
        "first_divergence",
    ):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            candidates.append(nested)
    for candidate in candidates:
        fields = {
            key: str(candidate.get(key) or "")
            for key in ("producer_digest", "validator_digest", "serializer_identity")
            if candidate.get(key)
        }
        citation_fields = {
            key: deepcopy(candidate[key])
            for key in (
                "citation_stage_trace",
                "frozen_citation_projection_trace",
                "citation_projection_source",
                "emitted_citation_evidence_identities",
            )
            if candidate.get(key)
        }
        if citation_fields:
            fields.update(citation_fields)
        if fields:
            return fields
    return {}


def _stage_list(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(stage) for stage in value.get("stages") or [] if isinstance(stage, Mapping)
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
