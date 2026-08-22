from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .artifact_identity import resolve_artifact_dir
from .artifact_publication import (
    ARTIFACT_COMPLETE_NAME,
    ARTIFACT_MANIFEST_NAME,
    atomic_write_bytes,
    file_sha256,
    verify_artifact_contract,
)
from .jsonl import iter_jsonl

RUNTIME_CONTRACT_SCHEMA_VERSION = "benchmark_runtime_contract.v1"
REQUIRED_JOB_ARTIFACTS = (
    "summary.json",
    "predictions.jsonl",
    "report.md",
    ARTIFACT_MANIFEST_NAME,
    ARTIFACT_COMPLETE_NAME,
)


def read_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"execution plan cannot be read: {path}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "benchmark_execution_plan.v1"
    ):
        raise ValueError(f"unsupported execution plan: {path}")
    if not isinstance(value.get("jobs"), list):
        raise ValueError("execution plan jobs must be a list")
    return value


def find_job(plan: dict[str, Any], job_key: str) -> dict[str, Any]:
    matches = [
        value
        for value in plan["jobs"]
        if isinstance(value, dict) and value.get("job_key") == job_key
    ]
    if len(matches) != 1:
        raise ValueError(f"execution plan must contain exactly one job: {job_key}")
    return matches[0]


def resolve_job_id(job: dict[str, Any], requested_job_id: str) -> str:
    requested = str(requested_job_id or "").strip()
    recorded = str(job.get("job_id") or "").strip()
    if requested and recorded and requested != recorded:
        raise ValueError(
            f"job ID does not match execution plan: requested={requested} recorded={recorded}"
        )
    resolved = requested or recorded
    if not resolved or any(character.isspace() for character in resolved):
        raise ValueError("a non-empty Slurm job ID is required")
    return resolved


def resolve_slurm_status(
    job_id: str,
    *,
    slurm_state: str | None,
    slurm_exit_code: str | None,
) -> tuple[str, str]:
    if slurm_state is not None or slurm_exit_code is not None:
        state = str(slurm_state or "").strip().split("+", 1)[0]
        exit_code = str(slurm_exit_code or "").strip()
        return state, exit_code
    try:
        result = subprocess.run(
            ["sacct", "-X", "-n", "-P", "-o", "State,ExitCode", "-j", job_id],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "UNKNOWN", ""
    if result.returncode != 0:
        return "UNKNOWN", ""
    for line in result.stdout.splitlines():
        fields = line.strip().split("|")
        if len(fields) >= 2 and fields[0]:
            return fields[0].split("+", 1)[0], fields[1].strip()
    return "UNKNOWN", ""


def inspect_artifact(
    job: dict[str, Any],
    *,
    artifact_dir: str | Path | None,
    job_id: str,
) -> dict[str, Any]:
    root = Path(str(job.get("output_root") or "")).resolve()
    if not str(job.get("output_root") or "").strip():
        raise ValueError("execution plan job has no output_root")
    expected = _expected_keys(job)
    candidate: Path | None
    failure_reasons: list[str] = []
    if artifact_dir is not None:
        candidate = Path(artifact_dir).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"artifact directory crosses job output boundary: {candidate}"
            ) from exc
    else:
        try:
            candidate = resolve_artifact_dir(
                root,
                suite_name=str(job["suite_name"]),
                job_id=job_id,
                required_artifacts=REQUIRED_JOB_ARTIFACTS,
            )
        except (OSError, ValueError) as exc:
            candidate = None
            failure_reasons.append(str(exc))

    if candidate is None or not candidate.is_dir():
        failure_reasons.append("complete artifact directory not found")
        return _artifact_result(candidate, failure_reasons=failure_reasons)

    try:
        missing_files = [
            name for name in REQUIRED_JOB_ARTIFACTS if not (candidate / name).is_file()
        ]
        if missing_files:
            raise ValueError(
                f"artifact directory is missing required files: {missing_files}"
            )
        marker = verify_artifact_contract(candidate)
        observed = _observed_prediction_keys(candidate)
        if observed != expected:
            raise ValueError(_key_mismatch(expected, observed))
        digest = str(marker.get("artifact_manifest_sha256") or "")
        if not digest:
            raise ValueError("artifact completion marker has no manifest digest")
        return {
            "artifact_complete": True,
            "artifact_digest": digest,
            "artifact_dir": str(candidate),
            "failure_reasons": [],
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure_reasons.append(str(exc))
        return _artifact_result(candidate, failure_reasons=failure_reasons)


def persist_runtime_contract(
    plan_path: Path,
    *,
    job_key: str,
    job_id: str,
    source_sha: str,
    runtime_contract_path: str | Path | None,
    existing_runtime_contract_path: Any,
) -> dict[str, str]:
    source_text = str(
        runtime_contract_path or existing_runtime_contract_path or ""
    ).strip()
    if not source_text:
        raise ValueError(
            "runtime contract path is required for completion reconciliation"
        )
    source = Path(source_text).resolve()
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"runtime contract cannot be read: {source}") from exc
    value = _decode_runtime_contract(source, payload)
    _validate_runtime_contract(
        value,
        job_key=job_key,
        job_id=job_id,
        source_sha=source_sha,
    )

    digest = hashlib.sha256(payload).hexdigest()
    durable_path = plan_path.parent / "runtime_contracts" / f"{_slug(job_key)}.json"
    _write_immutable_copy(durable_path, payload, digest)
    return {"path": str(durable_path), "sha256": digest, "failure_reason": ""}


def _observed_prediction_keys(candidate: Path) -> set[tuple[str, str]]:
    observed: set[tuple[str, str]] = set()
    for row in iter_jsonl(candidate / "predictions.jsonl"):
        if not isinstance(row, dict):
            raise ValueError("benchmark JSONL predictions must contain JSON objects")
        key = _prediction_key(row)
        if key in observed:
            raise ValueError(f"duplicate prediction key: {key}")
        observed.add(key)
    return observed


def _artifact_result(
    candidate: Path | None,
    *,
    failure_reasons: list[str],
) -> dict[str, Any]:
    return {
        "artifact_complete": False,
        "artifact_digest": "",
        "artifact_dir": str(candidate) if candidate else "",
        "failure_reasons": list(dict.fromkeys(failure_reasons)),
    }


def _key_mismatch(
    expected: set[tuple[str, str]],
    observed: set[tuple[str, str]],
) -> str:
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    return (
        f"key mismatch: missing={len(missing)} unexpected={len(unexpected)} "
        f"first_missing={missing[:1]} first_unexpected={unexpected[:1]}"
    )


def _decode_runtime_contract(source: Path, payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"runtime contract is not valid JSON: {source}") from exc
    if not isinstance(value, dict):
        raise ValueError("runtime contract must contain a JSON object")
    return value


def _validate_runtime_contract(
    value: dict[str, Any],
    *,
    job_key: str,
    job_id: str,
    source_sha: str,
) -> None:
    expected = {
        "contract_id": RUNTIME_CONTRACT_SCHEMA_VERSION,
        "source_sha": source_sha,
        "slurm_job_id": job_id,
        "execution_job_key": job_key,
    }
    for field, expected_value in expected.items():
        if not expected_value or value.get(field) != expected_value:
            raise ValueError(
                f"runtime contract {field} mismatch: "
                f"expected={expected_value!r} observed={value.get(field)!r}"
            )
    if value.get("git_dirty") is not False:
        raise ValueError("runtime contract records a dirty source checkout")
    for field in (
        "project_root",
        "runtime_dir",
        "sys.executable",
        "slide_cli.__file__",
        "ktem.__file__",
        "theflow_settings_source",
        "theflow_storage_prefix",
        "KH_APP_DATA_DIR",
        "THEFLOW_TEMP_PATH",
        "UV_PROJECT_ENVIRONMENT",
    ):
        if not str(value.get(field) or "").strip():
            raise ValueError(f"runtime contract is missing {field}")


def _write_immutable_copy(path: Path, payload: bytes, expected_digest: str) -> None:
    if path.exists() and file_sha256(path) != expected_digest:
        raise ValueError(f"durable runtime contract changed after publication: {path}")
    if path.is_symlink():
        raise ValueError(f"durable runtime contract must not be a symlink: {path}")
    if not path.is_file():
        atomic_write_bytes(path, payload)


def _expected_key(value: Any) -> tuple[str, str]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"execution plan contains an invalid expected key: {value!r}")
    key = (str(value[0]).strip(), str(value[1]).strip())
    if not key[0] or not key[1]:
        raise ValueError(f"execution plan contains a blank expected key: {value!r}")
    return key


def _expected_keys(job: dict[str, Any]) -> set[tuple[str, str]]:
    raw_keys = job.get("expected_keys")
    if not isinstance(raw_keys, list):
        raise ValueError("execution plan job expected_keys must be a list")
    keys = [_expected_key(value) for value in raw_keys]
    if len(keys) != len(set(keys)):
        raise ValueError("execution plan job expected_keys contains duplicates")
    if job.get("expected_key_count") != len(keys):
        raise ValueError(
            "execution plan expected_key_count does not match expected_keys"
        )
    expected_digest = str(job.get("expected_key_sha256") or "")
    if expected_digest != _key_sha256(keys):
        raise ValueError(
            "execution plan expected_key_sha256 does not match expected_keys"
        )
    return set(keys)


def _prediction_key(row: dict[str, Any]) -> tuple[str, str]:
    key = (
        str(row.get("example_id") or "").strip(),
        str(row.get("route") or "").strip(),
    )
    if not key[0] or not key[1]:
        raise ValueError("prediction is missing example_id or route")
    return key


def _key_sha256(keys: list[tuple[str, str]]) -> str:
    canonical = "\n".join(
        f"{example_id}\t{route_id}" for example_id, route_id in sorted(keys)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-")
    return slug or "job"
