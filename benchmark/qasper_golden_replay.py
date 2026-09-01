from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .qasper_golden_projection import REQUIRED_ROW_FIELDS, ROW_CONTRACT_ID
from .qasper_golden_projection import project_prediction as _project_prediction
from .jsonl import read_jsonl

CONTRACT_ID = "qasper_golden_replay.v1"
ANCHOR_REPLAY_SHA256 = (
    "62577842dfd44364bf40ce016711ed49d1bdb357413eaa007519876f4a9d911a"
)
RUN_ORDER = (
    "anchor_0343ba1",
    "architecture_fa31e4a",
    "failed_520ff98",
)
RUN_REVISIONS = {
    "anchor_0343ba1": "0343ba1eb5aef6640f8b773880be0867af275a36",
    "architecture_fa31e4a": "fa31e4ade7f8a94d2bab80cdd6d7f392a4d9d914",
    "failed_520ff98": "520ff98c57507b61b35bcaf07c9c971193637c0c",
}

_ADAPTER_FIELDS = {
    "terminal_outcome",
    "terminal_outcome_reason",
    "terminal_outcome_contract_violation",
    "terminal_outcome_classification",
}


@dataclass(frozen=True)
class ProjectedPredictionRun:
    label: str
    rows: list[dict[str, Any]]
    legacy_replay_sha256: str


def project_prediction(
    prediction: dict[str, Any],
    *,
    run_label: str,
) -> dict[str, Any]:
    return _project_prediction(
        prediction,
        run_label=run_label,
        allowed_run_labels=RUN_ORDER,
    )


def project_prediction_file(
    path: str | Path,
    *,
    run_label: str,
) -> ProjectedPredictionRun:
    source = _prediction_path(Path(path))
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    for value in read_jsonl(source):
        prediction = cast(dict[str, Any], value)
        if not first:
            digest.update(b",")
        digest.update(_canonical_json(_legacy_projection(prediction)))
        first = False
        rows.append(project_prediction(prediction, run_label=run_label))
    digest.update(b"]")
    return ProjectedPredictionRun(run_label, rows, digest.hexdigest())


def build_protected_sets(
    rows_by_run: Mapping[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    indexed = _validated_run_indexes(rows_by_run)
    anchor = indexed["anchor_0343ba1"]
    architecture = indexed["architecture_fa31e4a"]
    failed = indexed["failed_520ff98"]
    anchor_passing = {key for key, row in anchor.items() if _is_passing(row)}
    recovered = {
        key
        for key in anchor
        if key not in anchor_passing
        and (_is_passing(architecture[key]) or _is_passing(failed[key]))
    }
    true_sets = [
        {key for key, row in run.items() if _is_true_abstention(row)}
        for run in (anchor, architecture, failed)
    ]
    if not (true_sets[0] == true_sets[1] == true_sets[2]):
        raise ValueError("Golden replay true-abstention set drift across source runs.")
    return {
        "anchor_correct_answered": _protected_set(
            anchor_passing,
            "anchor answer_status=answered and metrics.native_score=1.0",
        ),
        "architecture_or_failed_new_passing": _protected_set(
            recovered,
            "fa31e4a or 520ff98 passes while 0343ba1 does not pass",
        ),
        "true_abstention_negative": _protected_set(
            true_sets[0],
            "verifier_observability.true_abstention=1 in all three source runs",
        ),
    }


def build_golden_contract(
    rows_by_run: Mapping[str, list[dict[str, Any]]],
    *,
    legacy_replay_hashes: Mapping[str, str],
    source_artifacts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    indexed = _validated_run_indexes(rows_by_run)
    sources = source_artifacts or {}
    runs: dict[str, dict[str, Any]] = {}
    for label in RUN_ORDER:
        rows = list(indexed[label].values())
        runs[label] = {
            "revision": RUN_REVISIONS[label],
            "source_artifact": str(sources.get(label) or ""),
            "prediction_count": len(rows),
            "prediction_key_sha256": _key_sha256(indexed[label]),
            "projection_sha256": projection_sha256(rows),
            "native_score_sha256": _native_score_sha256(rows),
            "legacy_replay_sha256": str(legacy_replay_hashes[label]),
            "terminal_outcome_counts": _value_counts(rows, "terminal_outcome"),
        }
    all_rows = [row for label in RUN_ORDER for row in indexed[label].values()]
    return {
        "contract_id": CONTRACT_ID,
        "row_contract_id": ROW_CONTRACT_ID,
        "run_order": list(RUN_ORDER),
        "total_projection_count": len(all_rows),
        "combined_projection_sha256": projection_sha256(all_rows),
        "runs": runs,
        "protected_sets": build_protected_sets(rows_by_run),
        "answer_status_patterns": _answer_status_patterns(indexed),
    }


def validate_golden_fixture(
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    if contract.get("contract_id") != CONTRACT_ID:
        raise ValueError("Golden replay contract id mismatch.")
    rows_by_run: dict[str, list[dict[str, Any]]] = {label: [] for label in RUN_ORDER}
    for row in rows:
        missing = set(REQUIRED_ROW_FIELDS) - set(row)
        if missing:
            raise ValueError(f"Golden replay row missing fields: {sorted(missing)}")
        label = str(row.get("run_label") or "")
        if label not in rows_by_run:
            raise ValueError(f"Unknown golden replay run label: {label}")
        rows_by_run[label].append(row)
    expected_runs = _mapping(contract.get("runs"))
    _validate_projection_hashes(rows_by_run, expected_runs)
    rebuilt = build_golden_contract(
        rows_by_run,
        legacy_replay_hashes={
            label: str(_mapping(expected_runs.get(label)).get("legacy_replay_sha256"))
            for label in RUN_ORDER
        },
        source_artifacts={
            label: str(_mapping(expected_runs.get(label)).get("source_artifact") or "")
            for label in RUN_ORDER
        },
    )
    for key in (
        "row_contract_id",
        "run_order",
        "total_projection_count",
        "combined_projection_sha256",
        "runs",
        "protected_sets",
        "answer_status_patterns",
    ):
        if rebuilt[key] != contract.get(key):
            raise ValueError(f"Golden replay contract mismatch: {key}")
    anchor_hash = rebuilt["runs"]["anchor_0343ba1"]["legacy_replay_sha256"]
    if anchor_hash != ANCHOR_REPLAY_SHA256:
        raise ValueError("Golden replay anchor legacy hash mismatch.")


def projection_sha256(rows: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=_projection_sort_key)
    return hashlib.sha256(_canonical_json(ordered)).hexdigest()


def legacy_prediction_projection_hash(
    predictions: Iterable[dict[str, Any]],
) -> str:
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, prediction in enumerate(predictions):
        if index:
            digest.update(b",")
        digest.update(_canonical_json(_legacy_projection(prediction)))
    digest.update(b"]")
    return digest.hexdigest()


def read_projection_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], value) for value in read_jsonl(path)]


def _validated_run_indexes(
    rows_by_run: Mapping[str, list[dict[str, Any]]],
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    if set(rows_by_run) != set(RUN_ORDER):
        raise ValueError(f"Golden replay requires exactly these runs: {RUN_ORDER}")
    indexes = {label: _index_run(rows_by_run[label], label) for label in RUN_ORDER}
    key_sets = [set(indexes[label]) for label in RUN_ORDER]
    if not (key_sets[0] == key_sets[1] == key_sets[2]):
        raise ValueError("Golden replay prediction key drift across source runs.")
    return indexes


def _index_run(
    rows: list[dict[str, Any]],
    label: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("run_label") != label:
            raise ValueError(f"Golden replay row label mismatch for {label}.")
        key = (str(row.get("example_id") or ""), str(row.get("route") or ""))
        if not all(key):
            raise ValueError("Golden replay prediction key is empty.")
        if key in indexed:
            raise ValueError(f"Golden replay duplicate prediction key: {key}")
        indexed[key] = row
    return indexed


def _protected_set(
    keys: set[tuple[str, str]],
    definition: str,
) -> dict[str, Any]:
    ordered = [list(key) for key in sorted(keys)]
    return {
        "definition": definition,
        "count": len(ordered),
        "keys": ordered,
        "keys_sha256": hashlib.sha256(_canonical_json(ordered)).hexdigest(),
    }


def _is_passing(row: dict[str, Any]) -> bool:
    return (
        row.get("answer_status") == "answered"
        and _number(row.get("native_score")) == 1.0
    )


def _is_true_abstention(row: dict[str, Any]) -> bool:
    observability = _mapping(row.get("verifier_observability"))
    return _integer(observability.get("true_abstention")) == 1


def _validate_projection_hashes(
    rows_by_run: Mapping[str, list[dict[str, Any]]],
    expected_runs: dict[str, Any],
) -> None:
    for label in RUN_ORDER:
        expected = _mapping(expected_runs.get(label))
        actual = projection_sha256(rows_by_run[label])
        if actual != expected.get("projection_sha256"):
            raise ValueError(f"Golden replay projection hash mismatch for {label}.")


def _native_score_sha256(rows: list[dict[str, Any]]) -> str:
    projection = [
        {
            "example_id": row.get("example_id"),
            "route": row.get("route"),
            "native_score": row.get("native_score"),
        }
        for row in sorted(rows, key=_projection_sort_key)
    ]
    return hashlib.sha256(_canonical_json(projection)).hexdigest()


def _value_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "unclassified")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _answer_status_patterns(
    indexed: Mapping[str, Mapping[tuple[str, str], dict[str, Any]]],
) -> dict[str, int]:
    patterns: dict[str, int] = {}
    for key in sorted(indexed[RUN_ORDER[0]]):
        pattern = "".join(
            "A" if indexed[label][key].get("answer_status") == "answered" else "X"
            for label in RUN_ORDER
        )
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return dict(sorted(patterns.items()))


def _key_sha256(indexed: Mapping[tuple[str, str], dict[str, Any]]) -> str:
    return hashlib.sha256(
        _canonical_json([list(key) for key in sorted(indexed)])
    ).hexdigest()


def _legacy_projection(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in prediction.items() if key not in _ADAPTER_FIELDS
    }


def _projection_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("run_label") or ""),
        str(row.get("example_id") or ""),
        str(row.get("route") or ""),
    )


def _prediction_path(path: Path) -> Path:
    return path / "predictions.jsonl" if path.is_dir() else path


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def _mapping(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
