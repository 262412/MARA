from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_publication import atomic_write_json, atomic_write_text

JOB_TABLE_COLUMNS = (
    "job_key",
    "group_key",
    "job_id",
    "wave_index",
    "dependency",
    "state",
    "kind",
    "dataset",
    "route",
    "shard_index",
    "num_shards",
    "limit",
    "timeout_seconds",
    "suite_name",
    "manifest",
    "manifest_sha256",
    "execution_manifest",
    "execution_manifest_sha256",
    "manifest_example_count",
    "selected_example_ids_json",
    "expected_route_ids_json",
    "expected_key_count",
    "expected_keys_json",
    "expected_key_sha256",
    "output_root",
    "contract_path",
    "artifact_complete",
    "artifact_digest",
    "artifact_dir",
    "exit_code",
    "slurm_state",
    "slurm_exit_code",
    "failure_reason",
    "producer_completion_state",
    "producer_exit_code",
    "producer_artifact_complete",
    "producer_artifact_digest",
    "producer_artifact_dir",
    "producer_failure_reason",
    "producer_completion_contract",
    "runtime_contract_path",
    "runtime_contract_sha256",
    "completion_reconciliation_contract",
)
_REQUIRED_JOB_FIELDS = frozenset(
    {
        "job_key",
        "group_key",
        "kind",
        "dataset",
        "route",
        "shard_index",
        "num_shards",
        "limit",
        "timeout_seconds",
        "suite_name",
        "manifest",
        "manifest_sha256",
        "manifest_example_count",
        "expected_key_count",
        "expected_key_sha256",
        "output_root",
        "contract_path",
    }
)


def write_plan_and_table(
    plan: dict[str, Any], plan_path: Path, table_path: Path
) -> None:
    atomic_write_json(plan_path, plan)
    rows = [_job_table_row(job) for job in plan.get("jobs", [])]
    lines = ["\t".join(JOB_TABLE_COLUMNS)]
    lines.extend(
        "\t".join(_table_value(row[column]) for column in JOB_TABLE_COLUMNS)
        for row in rows
    )
    atomic_write_text(table_path, "\n".join(lines) + "\n")


def _job_table_row(job: dict[str, Any]) -> dict[str, Any]:
    direct = {
        key: job[key] if key in _REQUIRED_JOB_FIELDS else job.get(key, "")
        for key in JOB_TABLE_COLUMNS
        if key
        not in {
            "selected_example_ids_json",
            "expected_route_ids_json",
            "expected_keys_json",
        }
    }
    direct["state"] = job.get("state", "PLANNED")
    direct["artifact_complete"] = job.get("artifact_complete", False)
    direct["producer_artifact_complete"] = job.get("producer_artifact_complete", False)
    direct.update(
        {
            "selected_example_ids_json": _compact_json(job["selected_example_ids"]),
            "expected_route_ids_json": _compact_json(job["expected_route_ids"]),
            "expected_keys_json": _compact_json(job["expected_keys"]),
        }
    )
    return direct


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _table_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
