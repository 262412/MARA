from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .artifact_identity import resolve_artifact_dir
from .artifact_publication import (
    ARTIFACT_COMPLETE_NAME,
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    file_sha256,
    publish_artifact_contract,
    verify_artifact_contract,
)
from .completion_reconciliation import (
    TERMINAL_RECONCILIATION_SCHEMA_VERSION,
    producer_completion_failure_reasons,
)
from .execution_plan import _write_plan_and_table
from .jsonl import iter_jsonl

REQUIRED_JOB_ARTIFACTS = (
    "summary.json",
    "predictions.jsonl",
    "report.md",
    "artifact_manifest.json",
    ARTIFACT_COMPLETE_NAME,
)


def synthesize_execution_plan(
    plan_path: str | Path,
    output_dir: str | Path,
    *,
    table_path: str | Path | None = None,
    validator_path: str | Path | None = None,
    require_all_usable: bool = False,
    require_slurm_clean: bool = False,
) -> dict[str, Any]:
    plan_path = Path(plan_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "benchmark_execution_plan.v1":
        raise ValueError(f"unsupported execution plan: {plan_path}")

    job_results = _collect_job_results(
        plan,
        require_all_usable=require_all_usable,
        require_slurm_clean=require_slurm_clean,
    )
    group_results = _synthesize_groups(
        plan,
        job_results,
        output_dir=output_dir,
        validator_path=Path(validator_path).resolve() if validator_path else None,
        require_all_usable=require_all_usable,
    )
    _update_execution_jobs(plan, job_results, require_slurm_clean)
    if table_path is None:
        table_path = plan_path.parent / "slurm_submission_jobs.tsv"
    _write_plan_and_table(plan, plan_path, Path(table_path).resolve())

    synthesis = {
        "schema_version": "benchmark_synthesis.v1",
        "plan_sha256": plan.get("plan_sha256"),
        "source_sha": plan.get("source_sha"),
        "job_count": len(plan.get("jobs", [])),
        "completed_job_count": sum(result["valid"] for result in job_results.values()),
        "expected_union_key_count": plan.get("expected_union_key_count"),
        **_aggregate_union_diagnostics(group_results),
        "valid": all(result["valid"] for result in group_results)
        and len(job_results) == len(plan.get("jobs", [])),
        "jobs": list(job_results.values()),
        "groups": group_results,
    }
    atomic_write_json(output_dir / "synthesis.json", synthesis)
    if not synthesis["valid"]:
        raise SystemExit(
            f"benchmark synthesis failed; see {output_dir / 'synthesis.json'}"
        )
    return synthesis


def _collect_job_results(
    plan: dict[str, Any],
    *,
    require_all_usable: bool,
    require_slurm_clean: bool,
) -> dict[str, dict[str, Any]]:
    return {
        job["job_key"]: _collect_job(
            job,
            require_all_usable=require_all_usable,
            require_slurm_clean=require_slurm_clean,
        )
        for job in plan.get("jobs", [])
    }


def _synthesize_groups(
    plan: dict[str, Any],
    job_results: dict[str, dict[str, Any]],
    *,
    output_dir: Path,
    validator_path: Path | None,
    require_all_usable: bool,
) -> list[dict[str, Any]]:
    results = []
    for group in plan.get("groups", []):
        matching_jobs = [
            job_results[job["job_key"]]
            for job in plan.get("jobs", [])
            if job["group_key"] == group["group_key"]
        ]
        results.append(
            _synthesize_group(
                group,
                matching_jobs,
                output_dir=output_dir,
                validator_path=validator_path,
                require_all_usable=require_all_usable,
            )
        )
    return results


def _update_execution_jobs(
    plan: dict[str, Any],
    job_results: dict[str, dict[str, Any]],
    require_slurm_clean: bool,
) -> None:
    for job in plan.get("jobs", []):
        result = job_results[job["job_key"]]
        job.update(
            {
                "state": "COMPLETED" if result["valid"] else "FAILED",
                "artifact_complete": bool(result.get("artifact_complete")),
                "artifact_digest": result.get("artifact_digest", ""),
                "artifact_dir": result.get("artifact_dir", ""),
                "exit_code": result.get("slurm_exit_code", ""),
                "slurm_state": result.get("slurm_state", ""),
                "slurm_exit_code": result.get("slurm_exit_code", ""),
                "failure_reason": result.get("failure_reason", ""),
                "completion_reconciliation_contract": (
                    TERMINAL_RECONCILIATION_SCHEMA_VERSION
                    if require_slurm_clean
                    else job.get("completion_reconciliation_contract", "")
                ),
            }
        )


def _aggregate_union_diagnostics(group_results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        key: sum(result.get(key, 0) for result in group_results)
        for key in (
            "union_key_count",
            "overlap_key_count",
            "missing_key_count",
            "unexpected_key_count",
        )
    }


def _collect_job(
    job: dict[str, Any],
    *,
    require_all_usable: bool,
    require_slurm_clean: bool,
) -> dict[str, Any]:
    slurm_state, slurm_exit_code = _slurm_status(str(job.get("job_id") or ""))
    result: dict[str, Any] = {
        "job_key": job["job_key"],
        "group_key": job["group_key"],
        "slurm_state": slurm_state,
        "slurm_exit_code": slurm_exit_code,
        "valid": False,
        "artifact_complete": False,
        "artifact_digest": "",
        "artifact_dir": "",
        "prediction_count": 0,
    }
    if require_slurm_clean and (slurm_state != "COMPLETED" or slurm_exit_code != "0:0"):
        result[
            "failure_reason"
        ] = f"slurm state={slurm_state} exit_code={slurm_exit_code}"
        return result
    root = Path(job["output_root"])
    artifact_dir = resolve_artifact_dir(
        root,
        suite_name=job["suite_name"],
        job_id=str(job.get("job_id") or ""),
        required_artifacts=REQUIRED_JOB_ARTIFACTS,
    )
    if artifact_dir is None:
        result["failure_reason"] = "complete artifact directory not found"
        return result
    try:
        marker = verify_artifact_contract(artifact_dir)
        prediction_count, mismatch = _inspect_job_predictions(
            job,
            artifact_dir,
            require_all_usable=require_all_usable,
        )
        if mismatch:
            result["failure_reason"] = mismatch
            return result
        artifact_digest = str(marker["artifact_manifest_sha256"])
        resolved_artifact_dir = str(artifact_dir.resolve())
        if require_slurm_clean:
            producer_reasons = producer_completion_failure_reasons(
                job,
                artifact_dir=resolved_artifact_dir,
                artifact_digest=artifact_digest,
                **_formal_audit_evidence(job),
                runtime_contract_path=str(job.get("runtime_contract_path") or ""),
                runtime_contract_sha256=str(job.get("runtime_contract_sha256") or ""),
            )
            if producer_reasons:
                result["failure_reason"] = "; ".join(producer_reasons)
                return result
        result.update(
            {
                "valid": True,
                "artifact_complete": True,
                "artifact_digest": artifact_digest,
                "artifact_dir": resolved_artifact_dir,
                "prediction_count": prediction_count,
                "producer_completion_state": job.get("producer_completion_state", ""),
                "runtime_contract_path": job.get("runtime_contract_path", ""),
                "runtime_contract_sha256": job.get("runtime_contract_sha256", ""),
                "completion_reconciliation_contract": (
                    TERMINAL_RECONCILIATION_SCHEMA_VERSION
                    if require_slurm_clean
                    else ""
                ),
            }
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result["failure_reason"] = str(exc)
    return result


def _formal_audit_evidence(job: dict[str, Any]) -> dict[str, str]:
    return {
        "formal_audit_status": str(job.get("formal_audit_status") or "not_present"),
        "formal_audit_path": str(job.get("formal_audit_path") or ""),
        "formal_audit_sha256": str(job.get("formal_audit_sha256") or ""),
    }


def _inspect_job_predictions(
    job: dict[str, Any],
    artifact_dir: Path,
    *,
    require_all_usable: bool,
) -> tuple[int, str]:
    observed: set[tuple[str, str]] = set()
    for row in _iter_prediction_rows(artifact_dir):
        key = _prediction_key(row)
        if key in observed:
            raise ValueError(f"duplicate prediction key: {key}")
        observed.add(key)
        if require_all_usable and not _prediction_is_usable(row):
            raise ValueError("job contains an unusable prediction")
    expected = {tuple(key) for key in job["expected_keys"]}
    mismatch = _key_mismatch_message(expected, observed) if observed != expected else ""
    return len(observed), mismatch


def _synthesize_group(
    group: dict[str, Any],
    job_results: list[dict[str, Any]],
    *,
    output_dir: Path,
    validator_path: Path | None,
    require_all_usable: bool,
) -> dict[str, Any]:
    group_dir = output_dir / _group_slug(group["group_key"])
    if group_dir.exists():
        raise FileExistsError(f"synthesis group already exists: {group_dir}")
    group_dir.mkdir(parents=True)
    execution_manifest = Path(group["execution_manifest"])
    observed_counts: Counter[tuple[str, str]] = Counter()
    try:
        if file_sha256(execution_manifest) != group["execution_manifest_sha256"]:
            raise ValueError("execution manifest digest changed after plan publication")

        atomic_write_jsonl(
            group_dir / "predictions.jsonl",
            _iter_merged_rows(job_results, require_all_usable, observed_counts),
        )
        diagnostics = _union_diagnostics(group, observed_counts)
        if any(
            diagnostics[key] != 0
            for key in (
                "overlap_key_count",
                "missing_key_count",
                "unexpected_key_count",
            )
        ):
            raise ValueError(
                "execution union check failed: "
                f"union={diagnostics['union_key_count']} "
                f"overlap={diagnostics['overlap_key_count']} "
                f"missing={diagnostics['missing_key_count']} "
                f"unexpected={diagnostics['unexpected_key_count']}"
            )
        atomic_write_json(
            group_dir / "summary.json",
            {
                "schema_version": "benchmark_synthesis_group.v1",
                "dataset": group["dataset"],
                "manifest": group["manifest"],
                "manifest_sha256": group["manifest_sha256"],
                "execution_manifest": str(execution_manifest),
                "num_predictions": diagnostics["union_key_count"],
                "expected_predictions": diagnostics["expected_key_count"],
            },
        )
        atomic_write_text(group_dir / "report.md", f"# {group['group_key']}\n")
        publish_artifact_contract(group_dir)
        verify_artifact_contract(group_dir)
        validation = _run_full_manifest_validator(
            group_dir,
            manifest=Path(group["execution_manifest"]),
            validator_path=validator_path,
            require_all_usable=require_all_usable,
            dataset=group["dataset"],
        )
        if validation.returncode != 0:
            raise ValueError(validation.stderr.strip() or validation.stdout.strip())
        return {
            "group_key": group["group_key"],
            "valid": True,
            "artifact_dir": str(group_dir),
            "artifact_digest": file_sha256(group_dir / "artifact_manifest.json"),
            "observed_key_count": diagnostics["union_key_count"],
            **diagnostics,
            "validator_stdout": validation.stdout,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "group_key": group["group_key"],
            "valid": False,
            "artifact_dir": str(group_dir),
            "failure_reason": str(exc),
            "observed_key_count": len(observed_counts),
            **_union_diagnostics(group, observed_counts),
        }


def _union_diagnostics(
    group: dict[str, Any],
    observed_counts: Counter[tuple[str, str]],
) -> dict[str, int]:
    expected = {
        (str(example_id), route_id)
        for example_id in group["selected_example_ids"]
        for route_id in group["manifest_route_ids"]
    }
    observed = set(observed_counts)
    return {
        "expected_key_count": len(expected),
        "union_key_count": len(observed),
        "overlap_key_count": sum(count > 1 for count in observed_counts.values()),
        "missing_key_count": len(expected - observed),
        "unexpected_key_count": len(observed - expected),
    }


def _run_full_manifest_validator(
    group_dir: Path,
    *,
    manifest: Path,
    validator_path: Path | None,
    require_all_usable: bool,
    dataset: str,
) -> subprocess.CompletedProcess[str]:
    if validator_path is None:
        validator_path = (
            Path(__file__).resolve().parents[1]
            / "scripts/slurm/validate_benchmark_predictions.py"
        )
    command = [
        sys.executable,
        str(validator_path),
        str(group_dir / "predictions.jsonl"),
        "--manifest",
        str(manifest),
        "--artifact-dir",
        str(group_dir),
        "--require-complete-marker",
    ]
    if require_all_usable:
        command.append("--require-all-usable")
    if "qasper" in dataset.casefold():
        command.extend(
            ["--require-qasper-answerability", "--qasper-manifest", str(manifest)]
        )
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _iter_prediction_rows(artifact_dir: Path) -> Iterator[dict[str, Any]]:
    for value in iter_jsonl(artifact_dir / "predictions.jsonl"):
        if not isinstance(value, dict):
            raise ValueError("benchmark JSONL predictions must contain JSON objects")
        yield dict(value)


def _iter_merged_rows(
    job_results: list[dict[str, Any]],
    require_all_usable: bool,
    observed_counts: Counter[tuple[str, str]],
) -> Iterator[dict[str, Any]]:
    for result in job_results:
        if not result["valid"]:
            continue
        for row in _iter_prediction_rows(Path(result["artifact_dir"])):
            key = _prediction_key(row)
            observed_counts[key] += 1
            if require_all_usable and not _prediction_is_usable(row):
                raise ValueError("merged group contains an unusable prediction")
            yield row


def _prediction_key(row: dict[str, Any]) -> tuple[str, str]:
    key = (
        str(row.get("example_id") or "").strip(),
        str(row.get("route") or "").strip(),
    )
    if not key[0] or not key[1]:
        raise ValueError("prediction is missing example_id or route")
    return key


def _key_mismatch_message(
    expected: set[tuple[str, str]], observed: set[tuple[str, str]]
) -> str:
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    return (
        f"key mismatch: missing={len(missing)} unexpected={len(unexpected)} "
        f"first_missing={missing[:1]} first_unexpected={unexpected[:1]}"
    )


def _prediction_is_usable(row: dict[str, Any]) -> bool:
    return (
        not row.get("error") and not row.get("skipped") and not row.get("skip_reason")
    )


def _slurm_status(job_id: str) -> tuple[str, str]:
    if not job_id:
        return "UNKNOWN", ""
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
            return fields[0].split("+")[0], fields[1]
    return "UNKNOWN", ""


def _group_slug(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in value)
