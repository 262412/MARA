from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.reasoning.mara_qasper_candidate import _record_candidate_response
from ktem.reasoning.mara_qasper_candidate_identity import candidate_digest

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest

_RESPONSE_FIELDS = (
    "status",
    "failure_reason",
    "raw_response",
    "raw_response_digest",
    "provider_output_digest",
    "raw_response_truncated",
    "cleaned_response",
    "raw_candidate",
    "provider_raw_candidate",
    "raw_candidate_failure_reason",
    "raw_candidate_digest",
    "typed_candidate",
    "typed_candidate_digest",
    "raw_candidate_identity_preserved",
    "requested_controlled_candidate",
    "cleaned_candidate",
    "verifier_input_candidate",
    "verifier_input_candidate_digest",
    "candidate_transport_identity_preserved",
    "candidate_transport_status",
    "verifier_execution_status",
    "auditor_execution_status",
    "verifier_transport_status",
    "auditor_transport_status",
    "finish_reason",
    "completion_tokens",
    "actual_input_tokens",
    "actual_input_token_count",
    "output_digest",
    "transformation_stages",
    "attempts",
)


def candidate_response_snapshot(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {field: deepcopy(candidate.get(field)) for field in _RESPONSE_FIELDS}


def replay_frozen_candidate_response(
    observation: dict[str, Any],
    frozen_response: Mapping[str, Any],
) -> dict[str, Any]:
    frozen = deepcopy(dict(frozen_response))
    raw_response = str(frozen.get("raw_response") or "")
    reasons = _raw_response_reasons(frozen, raw_response=raw_response)
    if raw_response:
        _record_replayed_response(observation, frozen, raw_response=raw_response)
    replayed = candidate_response_snapshot(observation)
    if raw_response:
        reasons.extend(_snapshot_reasons(frozen, replayed))
    unique_reasons = list(dict.fromkeys(reasons))
    observation["candidate_response_replay"] = {
        "contract_id": "qasper_frozen_candidate_response_replay.v1",
        "status": "matched" if not unique_reasons else "failed",
        "reasons": unique_reasons,
        "frozen_snapshot_digest": canonical_digest(frozen),
        "replayed_snapshot_digest": canonical_digest(replayed),
    }
    return observation


def _raw_response_reasons(
    frozen: Mapping[str, Any],
    *,
    raw_response: str,
) -> list[str]:
    reasons = []
    if not raw_response:
        reasons.append("candidate_raw_response_missing")
    if frozen.get("raw_response_truncated") is True:
        reasons.append("candidate_raw_response_truncated")
    if raw_response and candidate_digest(raw_response) != frozen.get(
        "raw_response_digest"
    ):
        reasons.append("candidate_raw_response_digest_mismatch")
    return reasons


def _record_replayed_response(
    observation: dict[str, Any],
    frozen: Mapping[str, Any],
    *,
    raw_response: str,
) -> None:
    identity = {
        key: str(observation.get(key) or "")
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
    response = SimpleNamespace(
        text=raw_response,
        completion_tokens=frozen.get("completion_tokens"),
        prompt_tokens=frozen.get("actual_input_tokens"),
        finish_reason=str(frozen.get("finish_reason") or ""),
    )
    _record_candidate_response(
        response,
        observation,
        identity,
        str(observation.get("input_digest") or ""),
        str(frozen.get("requested_controlled_candidate") or ""),
    )


def _snapshot_reasons(
    frozen: Mapping[str, Any],
    replayed: Mapping[str, Any],
) -> list[str]:
    reasons = []
    if frozen.get("raw_response_digest") != replayed.get("raw_response_digest"):
        reasons.append("candidate_raw_response_digest_mismatch")
    parser_fields = (
        "status",
        "failure_reason",
        "cleaned_response",
        "raw_candidate",
        "raw_candidate_failure_reason",
        "typed_candidate",
        "typed_candidate_digest",
        "raw_candidate_identity_preserved",
        "verifier_input_candidate",
        "candidate_transport_identity_preserved",
        "candidate_transport_status",
        "output_digest",
        "transformation_stages",
    )
    if any(frozen.get(field) != replayed.get(field) for field in parser_fields):
        reasons.append("candidate_parser_replay_mismatch")
    transport_fields = (
        "provider_output_digest",
        "provider_raw_candidate",
        "requested_controlled_candidate",
        "cleaned_candidate",
        "verifier_input_candidate_digest",
        "verifier_execution_status",
        "auditor_execution_status",
        "verifier_transport_status",
        "auditor_transport_status",
        "finish_reason",
        "completion_tokens",
        "actual_input_tokens",
        "actual_input_token_count",
    )
    if any(frozen.get(field) != replayed.get(field) for field in transport_fields):
        reasons.append("candidate_transport_replay_mismatch")
    if frozen.get("attempts") != replayed.get("attempts"):
        reasons.append("candidate_attempt_replay_mismatch")
    return reasons
