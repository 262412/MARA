from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark.jsonl import read_jsonl
from benchmark.qasper_causal_transaction import (
    qasper_causal_transaction_first_failure,
)


def qasper_causal_transaction_artifact_audit(
    run_dir: Path,
    predictions: list[dict[str, Any]],
    *,
    suite_kind: str,
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
    observations, violations = _audit_rows(rows, predictions)
    return (
        _audit(
            observations,
            violations,
            expected_count=len(predictions),
            observed_count=len(rows),
        ),
        violations,
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
    for key in expected_keys:
        row = indexed.get(key)
        if row is None:
            observations.append(_missing_observation(key))
            continue
        observation, violation = _transaction_observation(
            key,
            row.get("causal_transaction"),
        )
        observations.append(observation)
        if violation:
            violations.append(violation)
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


def _audit(
    observations: list[dict[str, Any]],
    violations: list[str],
    *,
    expected_count: int,
    observed_count: int,
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_causal_transaction_artifact_audit.v1",
        "applicable": True,
        "status": "passed" if not violations else "failed",
        "hard_rule": "stop_at_first_divergence",
        "expected_transaction_count": expected_count,
        "observed_transaction_count": observed_count,
        "complete_transaction_count": sum(
            observation.get("status") == "complete" for observation in observations
        ),
        "observations": observations,
        "violations": violations,
    }


def _not_applicable_audit() -> dict[str, Any]:
    return {
        "contract_id": "qasper_causal_transaction_artifact_audit.v1",
        "applicable": False,
        "status": "not_applicable",
        "hard_rule": "stop_at_first_divergence",
        "observations": [],
        "violations": [],
    }


def _route_key(value: Any) -> tuple[str, str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    return str(row.get("example_id") or ""), str(row.get("route") or "")
