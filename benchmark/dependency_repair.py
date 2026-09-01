from __future__ import annotations

import json
from pathlib import Path

from .artifact_publication import file_sha256
from .execution_plan import _write_plan_and_table

DEPENDENCY_REPAIR_CONTRACT = "benchmark_dependency_repair.v1"


def record_dependency_repair(
    plan_path: Path,
    table_path: Path,
    *,
    job_key: str,
    repair_record_path: Path,
) -> None:
    """Replace one stale dependency from a completed barrier repair record."""

    record_path = repair_record_path.resolve()
    repair = _read_dependency_repair(record_path)
    original_job_id = repair["original_job"]
    replacement_job_id = repair["replacement_job"]
    downstream_job_id = repair["downstream_job"]
    replacement_dependency = f"afterok:{replacement_job_id}"
    _validate_repair_state(repair, replacement_dependency)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    existing_repairs = _dependency_repair_audit(plan)
    if any(
        value.get("job_key") == job_key
        for value in existing_repairs
        if isinstance(value, dict)
    ):
        raise ValueError(f"dependency repair already recorded for job: {job_key}")
    _replace_dependency(
        plan,
        job_key=job_key,
        original_job_id=original_job_id,
        replacement_dependency=replacement_dependency,
        downstream_job_id=downstream_job_id,
        record_path=record_path,
    )
    existing_repairs.append(
        _repair_audit_entry(
            repair,
            job_key=job_key,
            replacement_dependency=replacement_dependency,
            record_path=record_path,
        )
    )
    _write_plan_and_table(plan, plan_path, table_path)


def _validate_repair_state(
    repair: dict[str, str],
    replacement_dependency: str,
) -> None:
    if repair["original_job_action"].lower() != "cancelled":
        raise ValueError("dependency repair original job must be cancelled")
    if repair["replacement_state"].upper() != "COMPLETED":
        raise ValueError("dependency repair replacement job must be COMPLETED")
    if repair["downstream_dependency"] != replacement_dependency:
        raise ValueError(
            "dependency repair downstream dependency does not match replacement job"
        )


def _dependency_repair_audit(plan: dict[str, object]) -> list[object]:
    existing = plan.get("dependency_repairs")
    if existing is None:
        existing = []
        plan["dependency_repairs"] = existing
    if not isinstance(existing, list):
        raise ValueError("execution plan dependency_repairs must be a list")
    return existing


def _replace_dependency(
    plan: dict[str, object],
    *,
    job_key: str,
    original_job_id: str,
    replacement_dependency: str,
    downstream_job_id: str,
    record_path: Path,
) -> None:
    jobs = plan.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("execution plan jobs must be a list")
    for job in jobs:
        if not isinstance(job, dict) or job.get("job_key") != job_key:
            continue
        if str(job.get("job_id") or "") != downstream_job_id:
            raise ValueError(
                "dependency repair downstream job does not match execution plan job"
            )
        if str(job.get("dependency") or "") != f"afterok:{original_job_id}":
            raise ValueError(
                "dependency repair original dependency does not match execution plan"
            )
        job["dependency"] = replacement_dependency
        job["dependency_repair_contract"] = DEPENDENCY_REPAIR_CONTRACT
        job["dependency_repair_record_sha256"] = file_sha256(record_path)
        return
    raise ValueError(f"execution plan job not found: {job_key}")


def _repair_audit_entry(
    repair: dict[str, str],
    *,
    job_key: str,
    replacement_dependency: str,
    record_path: Path,
) -> dict[str, str]:
    return {
        "contract_id": DEPENDENCY_REPAIR_CONTRACT,
        "job_key": job_key,
        "original_job_id": repair["original_job"],
        "replacement_job_id": repair["replacement_job"],
        "downstream_job_id": repair["downstream_job"],
        "downstream_dependency": replacement_dependency,
        "replacement_dependency_reason": repair["replacement_dependency"],
        "repair_record_path": str(record_path),
        "repair_record_sha256": file_sha256(record_path),
    }


def _read_dependency_repair(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"dependency repair record not found: {path}")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise ValueError(
                f"invalid dependency repair record line {line_number}: {raw_line!r}"
            )
        if key in values:
            raise ValueError(f"duplicate dependency repair field: {key}")
        values[key] = value
    required = {
        "original_job",
        "original_job_action",
        "replacement_job",
        "replacement_state",
        "replacement_dependency",
        "downstream_job",
        "downstream_dependency",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(
            f"dependency repair record missing fields: {', '.join(missing)}"
        )
    for key in ("original_job", "replacement_job", "downstream_job"):
        if not values[key].isdigit():
            raise ValueError(f"dependency repair {key} must be a numeric Slurm job ID")
    return values
