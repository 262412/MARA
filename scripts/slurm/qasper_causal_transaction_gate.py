from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmark.jsonl import read_jsonl
from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transactions,
    qasper_causal_transaction_first_failure,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    causal_replay_run_context,
    natural_causal_transaction_replay,
)
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context
from scripts.slurm.qasper_natural_semantic_pack_runtime import freeze_natural_pack
from scripts.slurm.qasper_retrieval_index_gate import retrieval_index_binding_audit

_REPLAY_CONTRACT = "qasper_natural_causal_transaction_replay.v1"
_REPLAY_STAGE_COUNT = len(QASPER_CAUSAL_TRANSACTION_STAGES)
_REPLAY_STAGE_NAME = QASPER_CAUSAL_TRANSACTION_STAGES[-1]


def qasper_causal_transaction_artifact_audit(
    run_dir: Path,
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
    retrieval_index_artifact_path: Path | None = None,
    retrieval_index_restore_audit_path: Path | None = None,
    expected_code_sha: str = "",
    expected_index_contract: str = "",
    expected_embedding_contract: str = "",
    require_retrieval_index_binding: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    if suite_kind != "qasper_debug":
        return _not_applicable_audit(), []
    trace_path = run_dir / "semantic_debug_traces.jsonl"
    if not trace_path.is_file():
        violation = "qasper_causal_transaction_artifact_missing"
        return (
            _audit(
                [],
                [violation],
                expected_count=len(predictions),
                observed_count=0,
            ),
            [violation],
        )
    try:
        rows = [row for row in read_jsonl(trace_path) if isinstance(row, dict)]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        violation = f"qasper_causal_transaction_artifact_invalid:{type(exc).__name__}"
        return (
            _audit(
                [],
                [violation],
                expected_count=len(predictions),
                observed_count=0,
            ),
            [violation],
        )
    retrieval_index_binding = retrieval_index_binding_audit(
        rows,
        artifact_path=retrieval_index_artifact_path,
        restore_audit_path=retrieval_index_restore_audit_path,
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
        required=require_retrieval_index_binding,
    )
    if require_retrieval_index_binding and (
        retrieval_index_binding.get("status") != "matched"
    ):
        violations = list(retrieval_index_binding.get("violations") or [])
        return (
            _audit(
                [],
                violations,
                expected_count=len(predictions),
                observed_count=len(rows),
                retrieval_index_binding=retrieval_index_binding,
            ),
            violations,
        )
    observations, violations = _audit_rows(rows, predictions)
    violations.extend(retrieval_index_binding.get("violations") or [])
    return (
        _audit(
            observations,
            list(dict.fromkeys(violations)),
            expected_count=len(predictions),
            observed_count=len(rows),
            retrieval_index_binding=retrieval_index_binding,
        ),
        list(dict.fromkeys(violations)),
    )


def _audit_rows(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    expected_keys = [_route_key(row) for row in predictions]
    observed_keys = [_route_key(row) for row in rows]
    expected_counts = Counter(expected_keys)
    observed_counts = Counter(observed_keys)
    violations = _cardinality_violations(expected_counts, observed_counts)
    indexed = {_route_key(row): row for row in rows}
    observations = []
    for key, prediction in zip(expected_keys, predictions):
        row = indexed.get(key)
        if row is None:
            online_observation = _missing_observation(key)
            replay_observation, replay_violation = _missing_replay_observation(key)
        else:
            online_observation, online_violation = _transaction_observation(
                key,
                row.get("causal_transaction"),
            )
            if online_violation:
                violations.append(online_violation)
            replay_observation, replay_violation = _replay_for_row(
                key,
                prediction,
                row,
            )
        observations.append(
            _combined_observation(online_observation, replay_observation)
        )
        if replay_violation:
            violations.append(replay_violation)
    return observations, list(dict.fromkeys(violations))


def _cardinality_violations(
    expected: Counter[tuple[str, str]],
    observed: Counter[tuple[str, str]],
) -> list[str]:
    violations = []
    for key in sorted(set(expected) | set(observed)):
        if expected[key] == observed[key] == 1:
            continue
        violations.append(
            "qasper_causal_transaction_key_count_mismatch:"
            f"{key[0]}:{key[1]}:{observed[key]}/{expected[key]}"
        )
    return violations


def _transaction_observation(
    key: tuple[str, str],
    value: Any,
) -> tuple[dict[str, Any], str]:
    transaction = dict(value) if isinstance(value, Mapping) else {}
    if _route_key(transaction.get("transaction_key")) != key:
        failure = {
            "stage_index": 0,
            "stage": "transaction_identity",
            "reason": "transaction_key_mismatch",
        }
    else:
        failure = qasper_causal_transaction_first_failure(transaction)
    observation = {
        "example_id": key[0],
        "route": key[1],
        "status": "complete" if not failure else "incomplete",
        "first_failure": failure,
        "later_stages_evaluated": not bool(failure),
    }
    if not failure:
        return observation, ""
    return observation, (
        "qasper_causal_transaction_first_failure:"
        f"{key[0]}:{key[1]}:stage_{failure.get('stage_index')}:"
        f"{failure.get('stage')}:{failure.get('reason')}"
    )


def _missing_observation(key: tuple[str, str]) -> dict[str, Any]:
    return {
        "example_id": key[0],
        "route": key[1],
        "status": "missing",
        "first_failure": {
            "stage_index": 0,
            "stage": "transaction_identity",
            "reason": "causal_transaction_missing",
        },
        "later_stages_evaluated": False,
    }


def _replay_for_row(
    key: tuple[str, str],
    prediction: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    replay, source = _attached_replay(trace, prediction)
    if replay is None:
        try:  # malformed snapshots must fail closed with an audit observation
            replay = _generate_replay(prediction, trace)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            return _replay_failure_observation(
                key,
                source="generation_failed",
                reason=f"{type(exc).__name__}:{exc}",
            )
        source = "generated"
    return _validate_replay(key, replay, source=source)


def _attached_replay(
    trace: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> tuple[Any, str]:
    for source, container in (("trace", trace), ("prediction", prediction)):
        if "causal_transaction_replay" not in container:
            continue
        replay = container.get("causal_transaction_replay")
        if replay is not None:
            return replay, source
    return None, ""


def _generate_replay(
    prediction: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    reference = _mapping(trace.get("causal_transaction"))
    if not reference:
        raise ValueError("online_causal_transaction_missing")
    run_context = causal_replay_run_context(prediction, reference)
    candidate_replay = candidate_replay_context(prediction)
    if candidate_replay.observation.get("complete") is not True:
        reasons = ",".join(
            str(reason)
            for reason in candidate_replay.observation.get("incompleteness_reasons")
            or []
        )
        raise ValueError(f"frozen_candidate_stage_snapshot_incomplete:{reasons}")
    if candidate_replay.observation.get("context_source") != "stage_input_snapshot":
        raise ValueError("legacy_candidate_stage_snapshot_not_replayable")
    if candidate_replay.observation.get("query_plan_source") != "stage_input_snapshot":
        raise ValueError("legacy_candidate_query_plan_not_replayable")
    run_provenance = _mapping(run_context.get("run_provenance"))
    code_identity = _mapping(run_provenance.get("git"))
    context = freeze_natural_pack(
        str(prediction.get("question") or ""),
        route=str(prediction.get("route") or ""),
        example_id=str(prediction.get("example_id") or ""),
        replay=candidate_replay,
        code_sha=str(code_identity.get("commit") or ""),
    )
    return natural_causal_transaction_replay(
        dict(prediction),
        context,
        run_context=run_context,
        preserve_frozen_semantic_projection=True,
    )


def _validate_replay(
    key: tuple[str, str],
    value: Any,
    *,
    source: str,
) -> tuple[dict[str, Any], str]:
    if not isinstance(value, Mapping):
        return _replay_failure_observation(
            key,
            source=source,
            reason="replay_record_invalid",
        )
    replay = dict(value)
    reference = _mapping(replay.get("reference_transaction"))
    local = _mapping(replay.get("local_replay_transaction"))
    comparison = compare_qasper_causal_transactions(reference, local)
    expected_status, failures = _replay_comparison_failures(replay, comparison)
    failures.extend(
        _replay_metadata_failures(key, replay, reference, local, comparison)
    )
    first_divergence = _first_divergence(comparison.get("first_divergence"))
    if failures and not first_divergence:
        first_divergence = dict(failures[0])
    observation = _replay_observation(
        key,
        replay,
        comparison,
        expected_status=expected_status,
        source=source,
        first_divergence=first_divergence,
        failed=bool(failures),
    )
    if failures:
        return observation, _replay_violation(key, failures[0])
    return observation, ""


def _replay_comparison_failures(
    replay: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    expected_status = "matched" if comparison.get("status") == "matched" else "failed"
    failures: list[dict[str, Any]] = []
    if comparison.get("status") != "matched":
        failures.append(
            dict(
                _mapping(comparison.get("first_divergence"))
                or {
                    "stage_index": int(comparison.get("compared_stage_count") or 0),
                    "stage": "replay_comparison",
                    "reason": "replay_not_matched",
                }
            )
        )
    if replay.get("status") != expected_status:
        failures.append(
            {
                "stage_index": int(comparison.get("compared_stage_count") or 0),
                "stage": "replay_comparison",
                "reason": "replay_status_mismatch",
            }
        )
    declared_comparison = _mapping(replay.get("comparison"))
    if not declared_comparison:
        failures.append(
            {
                "stage_index": 0,
                "stage": "replay_comparison",
                "reason": "replay_comparison_missing",
            }
        )
    elif declared_comparison.get("contract_id") != (
        "qasper_causal_transaction_comparison.v1"
    ):
        failures.append(
            {
                "stage_index": 0,
                "stage": "replay_comparison",
                "reason": "replay_comparison_contract_invalid",
            }
        )
    if declared_comparison and declared_comparison.get("status") != comparison.get(
        "status"
    ):
        failures.append(
            {
                "stage_index": int(comparison.get("compared_stage_count") or 0),
                "stage": "replay_comparison",
                "reason": "replay_comparison_status_mismatch",
            }
        )
    return expected_status, failures


def _replay_metadata_failures(
    key: tuple[str, str],
    replay: Mapping[str, Any],
    reference: Mapping[str, Any],
    local: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    contract_id = str(replay.get("contract_id") or "")
    if contract_id != _REPLAY_CONTRACT:
        failures.append(
            {
                "stage_index": 0,
                "stage": "replay_contract",
                "reason": "replay_contract_invalid",
            }
        )
    reference_key = _route_key(reference.get("transaction_key"))
    local_key = _route_key(local.get("transaction_key"))
    if reference_key != key or local_key != key:
        failures.append(
            {
                "stage_index": 0,
                "stage": "transaction_identity",
                "reason": "replay_transaction_key_mismatch",
            }
        )
    if replay.get("through_stage_index") != _REPLAY_STAGE_COUNT:
        failures.append(
            {
                "stage_index": int(replay.get("through_stage_index") or 0),
                "stage": str(replay.get("through_stage") or ""),
                "reason": "replay_not_through_stage12",
            }
        )
    if replay.get("through_stage") != _REPLAY_STAGE_NAME:
        failures.append(
            {
                "stage_index": _REPLAY_STAGE_COUNT,
                "stage": str(replay.get("through_stage") or ""),
                "reason": "replay_stage12_identity_mismatch",
            }
        )
    if replay.get("comparison_scope") != (
        f"causal_replay_through_{_REPLAY_STAGE_NAME}"
    ):
        failures.append(
            {
                "stage_index": _REPLAY_STAGE_COUNT,
                "stage": _REPLAY_STAGE_NAME,
                "reason": "replay_comparison_scope_invalid",
            }
        )
    if replay.get("hard_rule") != "stop_at_first_divergence":
        failures.append(
            {
                "stage_index": 0,
                "stage": "replay_comparison",
                "reason": "replay_hard_rule_invalid",
            }
        )
    return failures


def _replay_observation(
    key: tuple[str, str],
    replay: Mapping[str, Any],
    comparison: Mapping[str, Any],
    *,
    expected_status: str,
    source: str,
    first_divergence: Mapping[str, Any],
    failed: bool,
) -> dict[str, Any]:
    return {
        "example_id": key[0],
        "route": key[1],
        "status": "matched"
        if not failed and expected_status == "matched"
        else "failed",
        "replay_status": str(replay.get("status") or "missing"),
        "replay_contract_id": str(replay.get("contract_id") or ""),
        "replay_source": source,
        "through_stage_index": replay.get("through_stage_index"),
        "through_stage": replay.get("through_stage"),
        "compared_stage_count": int(comparison.get("compared_stage_count") or 0),
        "first_divergence": dict(first_divergence),
        "later_stages_evaluated": comparison.get("later_stages_evaluated") is True,
    }


def _replay_failure_observation(
    key: tuple[str, str],
    *,
    source: str,
    reason: str,
) -> tuple[dict[str, Any], str]:
    failure = {
        "stage_index": 0,
        "stage": "causal_transaction_replay",
        "reason": reason,
    }
    return (
        {
            "example_id": key[0],
            "route": key[1],
            "status": "missing",
            "replay_status": "missing",
            "replay_contract_id": "",
            "replay_source": source,
            "through_stage_index": 0,
            "through_stage": "",
            "compared_stage_count": 0,
            "first_divergence": failure,
            "later_stages_evaluated": False,
        },
        _replay_violation(key, failure),
    )


def _missing_replay_observation(
    key: tuple[str, str],
) -> tuple[dict[str, Any], str]:
    return _replay_failure_observation(
        key,
        source="online_transaction_missing",
        reason="online_causal_transaction_missing",
    )


def _replay_violation(key: tuple[str, str], failure: Mapping[str, Any]) -> str:
    return (
        "qasper_natural_causal_transaction_replay_failure:"
        f"{key[0]}:{key[1]}:stage_{failure.get('stage_index')}:"
        f"{failure.get('stage')}:{failure.get('reason')}"
    )


def _first_divergence(value: Any) -> dict[str, Any]:
    divergence = _mapping(value)
    return {
        key: divergence[key]
        for key in (
            "stage_index",
            "stage",
            "reason",
            "producer_digest",
            "validator_digest",
            "serializer_identity",
        )
        if key in divergence
    }


def _combined_observation(
    online: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    observation = dict(online)
    observation["causal_transaction_status"] = online.get("status")
    observation["causal_transaction_first_failure"] = deepcopy(
        online.get("first_failure") or {}
    )
    observation.update(dict(replay))
    return observation


def _audit(
    observations: list[dict[str, Any]],
    violations: list[str],
    *,
    expected_count: int,
    observed_count: int,
    retrieval_index_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_causal_transaction_artifact_audit.v1",
        "applicable": True,
        "status": "passed" if not violations else "failed",
        "hard_rule": "stop_at_first_divergence",
        "expected_transaction_count": expected_count,
        "observed_transaction_count": observed_count,
        "complete_transaction_count": sum(
            observation.get("causal_transaction_status") == "complete"
            for observation in observations
        ),
        "replay_expected_transaction_count": expected_count,
        "replay_matched_transaction_count": sum(
            observation.get("status") == "matched" for observation in observations
        ),
        "retrieval_index_binding_audit": dict(retrieval_index_binding or {}),
        "observations": observations,
        "violations": violations,
    }


def _not_applicable_audit() -> dict[str, Any]:
    return {
        "contract_id": "qasper_causal_transaction_artifact_audit.v1",
        "applicable": False,
        "status": "not_applicable",
        "hard_rule": "stop_at_first_divergence",
        "expected_transaction_count": 0,
        "observed_transaction_count": 0,
        "complete_transaction_count": 0,
        "replay_expected_transaction_count": 0,
        "replay_matched_transaction_count": 0,
        "retrieval_index_binding_audit": {
            "contract_id": "qasper_retrieval_index_binding_audit.v1",
            "status": "not_applicable",
            "hard_rule": "stop_at_first_divergence",
            "observations": [],
            "violations": [],
        },
        "observations": [],
        "violations": [],
    }


def _route_key(value: Any) -> tuple[str, str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    return str(row.get("example_id") or ""), str(row.get("route") or "")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
