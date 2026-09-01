"""Freeze and verify the real QASPER Stage 2 retrieval/index boundary."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from ktem.docqa.canonical_serialization import (
    CANONICAL_SERIALIZER_IDENTITY,
    canonical_digest,
)

from benchmark.qasper_causal_transaction import compare_qasper_causal_transaction_prefix
from benchmark.qasper_causal_transaction_stages import (
    QASPER_RETRIEVAL_TRACE_IDENTITY_CONTRACT,
    retrieval_trace_semantic_projection,
    retrieval_trace_telemetry_projection,
    stage_comparison_payload,
)

ARTIFACT_CONTRACT = "qasper_retrieval_index_artifact.v1"
INDEX_SNAPSHOT_CONTRACT = "qasper_index_snapshot.v1"
BINDING_AUDIT_CONTRACT = "qasper_retrieval_index_binding_audit.v1"
RESTORE_AUDIT_CONTRACT = "qasper_retrieval_index_restore_audit.v1"
_STAGE_INDEX = 2
_STAGE_NAME = "retrieval_and_ranking"
_REQUIRED_SOURCE_ARTIFACTS = {"predictions", "semantic_debug_traces"}


def build_retrieval_index_artifact(
    trace_rows: Sequence[Mapping[str, Any]],
    *,
    code_sha: str,
    index_contract: str,
    embedding_contract: str,
    index_snapshot: Mapping[str, Any],
    source_artifacts: Mapping[str, Any],
    required_route: str = "text_rag",
) -> dict[str, Any]:
    """Build an immutable artifact from genuine online causal transactions."""

    if not _git_sha(code_sha):
        raise ValueError("retrieval_index_artifact_code_sha_invalid")
    if not str(index_contract or "").strip():
        raise ValueError("retrieval_index_artifact_index_contract_missing")
    if not str(embedding_contract or "").strip():
        raise ValueError("retrieval_index_artifact_embedding_contract_missing")
    snapshot = deepcopy(dict(index_snapshot))
    snapshot_reasons = _index_snapshot_violations(snapshot)
    if snapshot_reasons:
        raise ValueError(snapshot_reasons[0])
    sources = deepcopy(dict(source_artifacts))
    source_reasons = _source_artifact_violations(sources)
    if source_reasons:
        raise ValueError(source_reasons[0])

    records = [
        _stage2_record(row, expected_code_sha=code_sha)
        for row in trace_rows
        if not required_route or _route_key(row)[1] == required_route
    ]
    records.sort(key=lambda value: (value["example_id"], value["route"]))
    keys = [(record["example_id"], record["route"]) for record in records]
    counts = Counter(keys)
    if not records:
        raise ValueError("retrieval_index_artifact_stage2_records_missing")
    duplicate = next((key for key, count in counts.items() if count != 1), None)
    if duplicate is not None:
        raise ValueError(
            "retrieval_index_artifact_stage2_record_duplicate:"
            f"{duplicate[0]}:{duplicate[1]}"
        )

    artifact = {
        "contract_id": ARTIFACT_CONTRACT,
        "serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
        "code_sha": code_sha,
        "required_route": required_route,
        "index_contract": str(index_contract),
        "embedding_contract": str(embedding_contract),
        "index_snapshot": snapshot,
        "source_artifacts": sources,
        "stage2_record_count": len(records),
        "stage2_records": records,
    }
    artifact["artifact_digest"] = canonical_digest(artifact)
    return artifact


def audit_retrieval_index_binding(
    artifact: Mapping[str, Any],
    trace_rows: Sequence[Mapping[str, Any]],
    *,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
    required_route: str,
    pre_stage2_violations: Sequence[str] = (),
) -> dict[str, Any]:
    """Compare online Stage 2 to one artifact and stop at its first difference."""

    frozen = deepcopy(dict(artifact))
    violations = _binding_identity_violations(
        frozen,
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
        required_route=required_route,
    )
    violations.extend(str(reason) for reason in pre_stage2_violations if str(reason))
    if violations:
        return _binding_audit(
            frozen,
            [],
            list(dict.fromkeys(violations)),
            expected_code_sha=expected_code_sha,
            expected_index_contract=expected_index_contract,
            expected_embedding_contract=expected_embedding_contract,
            required_route=required_route,
        )

    (
        expected_by_key,
        selected_rows,
        observed_counts,
        count_violations,
    ) = _stage2_row_sets(frozen, trace_rows, required_route=required_route)
    violations.extend(count_violations)

    observed_by_key = {_route_key(row): row for row in selected_rows}
    observations: list[dict[str, Any]] = []
    for key in sorted(expected_by_key):
        row = observed_by_key.get(key)
        if row is None or observed_counts[key] != 1:
            continue
        try:
            observed = _stage2_record(row, expected_code_sha=expected_code_sha)
        except ValueError as exc:
            observation = _divergence_observation(
                key,
                reason=f"online_stage2_integrity_invalid:{exc}",
            )
        else:
            observation = _compare_stage2_record(expected_by_key[key], observed)
        observations.append(observation)
        if observation["status"] != "matched":
            first = _mapping(observation.get("first_divergence"))
            violations.append(
                "retrieval_index_artifact_stage2_mismatch:"
                f"{key[0]}:{key[1]}:{first.get('reason', 'stage2_mismatch')}"
            )
    return _binding_audit(
        frozen,
        observations,
        list(dict.fromkeys(violations)),
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
        required_route=required_route,
    )


def _stage2_row_sets(
    artifact: Mapping[str, Any],
    trace_rows: Sequence[Mapping[str, Any]],
    *,
    required_route: str,
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    list[Mapping[str, Any]],
    Counter[tuple[str, str]],
    list[str],
]:
    records = [deepcopy(dict(row)) for row in artifact.get("stage2_records") or []]
    expected = {_route_key(record): record for record in records}
    selected = [
        row
        for row in trace_rows
        if not required_route or _route_key(row)[1] == required_route
    ]
    observed_counts = Counter(_route_key(row) for row in selected)
    expected_counts = Counter(expected.keys())
    violations = [
        "retrieval_index_artifact_stage2_key_count_mismatch:"
        f"{key[0]}:{key[1]}:{observed_counts[key]}/{expected_counts[key]}"
        for key in sorted(set(expected_counts) | set(observed_counts))
        if expected_counts[key] != 1 or observed_counts[key] != 1
    ]
    return expected, selected, observed_counts, violations


def load_retrieval_index_artifact(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("retrieval_index_artifact_object_required")
    return value


def _stage2_record(
    trace_row: Mapping[str, Any],
    *,
    expected_code_sha: str,
) -> dict[str, Any]:
    transaction = _mapping(trace_row.get("causal_transaction"))
    key = _route_key(transaction.get("transaction_key"))
    if not all(key) or key != _route_key(trace_row):
        raise ValueError("stage2_transaction_key_mismatch")
    comparison = compare_qasper_causal_transaction_prefix(
        transaction,
        transaction,
        through_stage=_STAGE_INDEX,
    )
    if comparison.get("status") != "matched_prefix":
        first = _mapping(comparison.get("first_divergence"))
        raise ValueError(
            "stage2_transaction_prefix_invalid:"
            f"{first.get('reason', 'prefix_not_matched')}"
        )
    stages = transaction.get("stages")
    if not isinstance(stages, list) or len(stages) < 12:
        raise ValueError("stage2_transaction_stages_missing")
    stage = _mapping(stages[_STAGE_INDEX - 1])
    payload = _mapping(stage.get("payload"))
    _validate_stage2_payload(stage, payload)
    _validate_source_code_identity(stages, expected_code_sha=expected_code_sha)
    return {
        "example_id": key[0],
        "route": key[1],
        "raw_retrieval_records": deepcopy(payload["raw_retrieval_records"]),
        "raw_retrieval_records_digest": payload["raw_retrieval_records_digest"],
        "retrieval_trace_identity_contract": payload[
            "retrieval_trace_identity_contract"
        ],
        "retrieval_trace": deepcopy(payload["retrieval_trace"]),
        "retrieval_trace_digest": payload["retrieval_trace_digest"],
        "retrieval_trace_semantic_digest": payload["retrieval_trace_semantic_digest"],
        "retrieval_trace_telemetry_digest": payload["retrieval_trace_telemetry_digest"],
        "production_input_records": deepcopy(payload["production_input_records"]),
        "production_input_records_digest": payload["production_input_records_digest"],
        "ranking_source": payload["ranking_source"],
        "ranking": deepcopy(payload["ranking"]),
        "ranking_digest": payload["ranking_digest"],
        "stage_payload_digest": stage["payload_digest"],
        "stage_comparison_digest": stage["comparison_digest"],
    }


def _validate_stage2_payload(
    stage: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    if stage.get("stage_index") != _STAGE_INDEX or stage.get("stage") != _STAGE_NAME:
        raise ValueError("stage2_identity_invalid")
    if stage.get("status") != "complete" or payload.get("status") != "complete":
        raise ValueError("stage2_incomplete")
    required_lists = (
        "raw_retrieval_records",
        "retrieval_trace",
        "production_input_records",
        "ranking",
    )
    if any(not isinstance(payload.get(key), list) for key in required_lists):
        raise ValueError("stage2_records_missing")
    digest_values = {
        "raw_retrieval_records": "raw_retrieval_records_digest",
        "retrieval_trace": "retrieval_trace_digest",
        "production_input_records": "production_input_records_digest",
        "ranking": "ranking_digest",
    }
    for value_key, digest_key in digest_values.items():
        if canonical_digest(payload[value_key]) != payload.get(digest_key):
            raise ValueError(f"stage2_{digest_key}_invalid")
    if (
        payload.get("retrieval_trace_identity_contract")
        != QASPER_RETRIEVAL_TRACE_IDENTITY_CONTRACT
    ):
        raise ValueError("stage2_retrieval_trace_identity_contract_invalid")
    retrieval_trace = payload["retrieval_trace"]
    if canonical_digest(
        retrieval_trace_semantic_projection(retrieval_trace)
    ) != payload.get("retrieval_trace_semantic_digest"):
        raise ValueError("stage2_retrieval_trace_semantic_digest_invalid")
    if canonical_digest(
        retrieval_trace_telemetry_projection(retrieval_trace)
    ) != payload.get("retrieval_trace_telemetry_digest"):
        raise ValueError("stage2_retrieval_trace_telemetry_digest_invalid")
    if canonical_digest(payload) != stage.get("payload_digest"):
        raise ValueError("stage2_payload_digest_invalid")
    if canonical_digest(stage_comparison_payload(_STAGE_NAME, payload)) != stage.get(
        "comparison_digest"
    ):
        raise ValueError("stage2_comparison_digest_invalid")


def _validate_source_code_identity(
    stages: Sequence[Any],
    *,
    expected_code_sha: str,
) -> None:
    stage = _mapping(stages[11])
    payload = _mapping(stage.get("payload"))
    provenance = _mapping(payload.get("run_provenance"))
    code = _mapping(provenance.get("code_identity"))
    if stage.get("stage_index") != 12 or stage.get("stage") != (
        "run_provenance_and_artifact"
    ):
        raise ValueError("stage12_identity_invalid")
    if canonical_digest(payload) != stage.get("payload_digest"):
        raise ValueError("stage12_payload_digest_invalid")
    if code.get("sha") != expected_code_sha:
        raise ValueError("stage12_code_sha_mismatch")
    if code.get("worktree_clean") is not True:
        raise ValueError("stage12_worktree_not_clean")


def _compare_stage2_record(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    key = (str(expected.get("example_id") or ""), str(expected.get("route") or ""))
    comparisons = (
        (
            "raw_retrieval_records",
            "raw_retrieval_records_digest",
            "raw_retrieval_records_mismatch",
        ),
        ("ranking", "ranking_digest", "ranking_mismatch"),
        (
            "retrieval_trace_semantic_projection",
            "retrieval_trace_semantic_digest",
            "retrieval_trace_semantic_mismatch",
        ),
        (
            "production_input_records",
            "production_input_records_digest",
            "production_input_records_mismatch",
        ),
    )
    for value_key, digest_key, reason in comparisons:
        expected_value = expected.get(value_key)
        observed_value = observed.get(value_key)
        if value_key == "retrieval_trace_semantic_projection":
            expected_value = retrieval_trace_semantic_projection(
                list(expected.get("retrieval_trace") or [])
            )
            observed_value = retrieval_trace_semantic_projection(
                list(observed.get("retrieval_trace") or [])
            )
        if expected_value != observed_value:
            return _divergence_observation(
                key,
                reason=reason,
                producer_digest=str(expected.get(digest_key) or ""),
                validator_digest=str(observed.get(digest_key) or ""),
            )
        if expected.get(digest_key) != observed.get(digest_key):
            return _divergence_observation(
                key,
                reason=f"{digest_key}_mismatch",
                producer_digest=str(expected.get(digest_key) or ""),
                validator_digest=str(observed.get(digest_key) or ""),
            )
    for key_name, reason in (
        ("ranking_source", "ranking_source_mismatch"),
        (
            "retrieval_trace_identity_contract",
            "retrieval_trace_identity_contract_mismatch",
        ),
        ("stage_comparison_digest", "stage_comparison_digest_mismatch"),
    ):
        if expected.get(key_name) != observed.get(key_name):
            return _divergence_observation(
                key,
                reason=reason,
                producer_digest=str(expected.get(key_name) or ""),
                validator_digest=str(observed.get(key_name) or ""),
            )
    return {
        "example_id": key[0],
        "route": key[1],
        "status": "matched",
        "first_divergence": {},
        "later_stages_evaluated": False,
    }


def _divergence_observation(
    key: tuple[str, str],
    *,
    reason: str,
    producer_digest: str = "",
    validator_digest: str = "",
) -> dict[str, Any]:
    divergence = {
        "stage_index": _STAGE_INDEX,
        "stage": _STAGE_NAME,
        "reason": reason,
    }
    if producer_digest or validator_digest:
        divergence.update(
            {
                "producer_digest": producer_digest,
                "validator_digest": validator_digest,
                "serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
            }
        )
    return {
        "example_id": key[0],
        "route": key[1],
        "status": "diverged",
        "first_divergence": divergence,
        "later_stages_evaluated": False,
    }


def _binding_audit(
    artifact: Mapping[str, Any],
    observations: list[dict[str, Any]],
    violations: list[str],
    *,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
    required_route: str,
) -> dict[str, Any]:
    return {
        "contract_id": BINDING_AUDIT_CONTRACT,
        "status": "matched" if not violations else "failed",
        "hard_rule": "stop_at_first_divergence",
        "expected_code_sha": expected_code_sha,
        "expected_index_contract": expected_index_contract,
        "expected_embedding_contract": expected_embedding_contract,
        "artifact_index_contract": str(artifact.get("index_contract") or ""),
        "artifact_embedding_contract": str(artifact.get("embedding_contract") or ""),
        "required_route": required_route,
        "artifact_digest": str(artifact.get("artifact_digest") or ""),
        "index_snapshot_tree_digest": str(
            _mapping(artifact.get("index_snapshot")).get("tree_digest") or ""
        ),
        "expected_record_count": int(artifact.get("stage2_record_count") or 0),
        "observed_record_count": len(observations),
        "matched_record_count": sum(
            observation.get("status") == "matched" for observation in observations
        ),
        "observations": observations,
        "violations": violations,
    }


def _artifact_violations(artifact: Mapping[str, Any]) -> list[str]:
    reasons = []
    if artifact.get("contract_id") != ARTIFACT_CONTRACT:
        reasons.append("retrieval_index_artifact_integrity_invalid:contract_invalid")
    if artifact.get("serializer_identity") != CANONICAL_SERIALIZER_IDENTITY:
        reasons.append("retrieval_index_artifact_integrity_invalid:serializer_invalid")
    digest = str(artifact.get("artifact_digest") or "")
    payload = {
        key: value for key, value in artifact.items() if key != "artifact_digest"
    }
    if not _sha256(digest) or canonical_digest(payload) != digest:
        reasons.append(
            "retrieval_index_artifact_integrity_invalid:artifact_digest_mismatch"
        )
    if not _git_sha(artifact.get("code_sha")):
        reasons.append("retrieval_index_artifact_integrity_invalid:code_sha_invalid")
    records = artifact.get("stage2_records")
    if not isinstance(records, list) or len(records) != artifact.get(
        "stage2_record_count"
    ):
        reasons.append(
            "retrieval_index_artifact_integrity_invalid:record_count_invalid"
        )
    reasons.extend(
        f"retrieval_index_artifact_integrity_invalid:{reason}"
        for reason in _index_snapshot_violations(
            _mapping(artifact.get("index_snapshot"))
        )
    )
    reasons.extend(
        f"retrieval_index_artifact_integrity_invalid:{reason}"
        for reason in _source_artifact_violations(
            _mapping(artifact.get("source_artifacts"))
        )
    )
    return list(dict.fromkeys(reasons))


def retrieval_index_artifact_violations(
    artifact: Mapping[str, Any],
) -> list[str]:
    """Return immutable artifact-integrity violations for other gate modules."""

    return _artifact_violations(artifact)


def _binding_identity_violations(
    artifact: Mapping[str, Any],
    *,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
    required_route: str,
) -> list[str]:
    reasons = _artifact_violations(artifact)
    for key, expected in (
        ("code_sha", expected_code_sha),
        ("index_contract", expected_index_contract),
        ("embedding_contract", expected_embedding_contract),
        ("required_route", required_route),
    ):
        if str(artifact.get(key) or "") != expected:
            label = "route" if key == "required_route" else key
            reasons.append(f"retrieval_index_artifact_{label}_mismatch")
    return reasons


def _index_snapshot_violations(snapshot: Mapping[str, Any]) -> list[str]:
    reasons = []
    if snapshot.get("contract_id") != INDEX_SNAPSHOT_CONTRACT:
        reasons.append("index_snapshot_contract_invalid")
    if not str(snapshot.get("path") or ""):
        reasons.append("index_snapshot_path_missing")
    if not _sha256(snapshot.get("tree_digest")):
        reasons.append("index_snapshot_tree_digest_missing")
    for key in ("file_count", "total_bytes"):
        value = snapshot.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            reasons.append(f"index_snapshot_{key}_invalid")
    if int(snapshot.get("file_count") or 0) == 0:
        reasons.append("index_snapshot_empty")
    return reasons


def _source_artifact_violations(sources: Mapping[str, Any]) -> list[str]:
    reasons = []
    if set(sources) != _REQUIRED_SOURCE_ARTIFACTS:
        reasons.append("source_artifact_set_invalid")
    for name in sorted(_REQUIRED_SOURCE_ARTIFACTS):
        source = _mapping(sources.get(name))
        if not str(source.get("path") or ""):
            reasons.append(f"source_artifact_path_missing:{name}")
        if not _sha256(source.get("sha256")):
            reasons.append(f"source_artifact_digest_missing:{name}")
    return reasons


def _route_key(value: Any) -> tuple[str, str]:
    row = _mapping(value)
    return str(row.get("example_id") or ""), str(row.get("route") or "")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _git_sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(
        character in "0123456789abcdef" for character in text
    )
