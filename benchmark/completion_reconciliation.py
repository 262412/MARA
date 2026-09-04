from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Slurm producers run on POSIX hosts.
    fcntl = None  # type: ignore[assignment]

from .artifact_publication import file_sha256
from .completion_evidence import find_job as _find_job
from .completion_evidence import inspect_artifact as _inspect_artifact
from .completion_evidence import persist_runtime_contract as _persist_runtime_contract
from .completion_evidence import read_plan as _read_plan
from .completion_evidence import resolve_job_id as _resolve_job_id
from .completion_evidence import resolve_slurm_status as _resolve_slurm_status
from .execution_plan import _write_plan_and_table

PRODUCER_COMPLETION_SCHEMA_VERSION = "benchmark_producer_completion.v2"
TERMINAL_RECONCILIATION_SCHEMA_VERSION = "benchmark_terminal_reconciliation.v2"
_TERMINAL_STATES = {
    "BOOT_FAIL",
    "CANCELLED",
    "COMPLETED",
    "DEADLINE",
    "FAILED",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "REVOKED",
    "SPECIAL_EXIT",
    "TIMEOUT",
}


def reconcile_job_completion(
    plan_path: str | Path,
    table_path: str | Path,
    *,
    job_key: str,
    job_id: str = "",
    artifact_dir: str | Path | None = None,
    runtime_contract_path: str | Path | None = None,
    slurm_state: str | None = None,
    slurm_exit_code: str | None = None,
    producer_exit_code: int | None = None,
    producer_only: bool = False,
) -> dict[str, Any]:
    """Serialize producer updates so concurrent jobs cannot lose ledger rows."""

    with _ledger_lock(Path(plan_path).resolve()):
        return _reconcile_job_completion(
            plan_path,
            table_path,
            job_key=job_key,
            job_id=job_id,
            artifact_dir=artifact_dir,
            runtime_contract_path=runtime_contract_path,
            slurm_state=slurm_state,
            slurm_exit_code=slurm_exit_code,
            producer_exit_code=producer_exit_code,
            producer_only=producer_only,
        )


def _reconcile_job_completion(
    plan_path: str | Path,
    table_path: str | Path,
    *,
    job_key: str,
    job_id: str = "",
    artifact_dir: str | Path | None = None,
    runtime_contract_path: str | Path | None = None,
    slurm_state: str | None = None,
    slurm_exit_code: str | None = None,
    producer_exit_code: int | None = None,
    producer_only: bool = False,
) -> dict[str, Any]:
    """Reconcile one producer's terminal state into the durable execution ledger.

    The function validates every input before mutating the plan.  A terminal
    Slurm observation with an invalid or incomplete artifact is recorded as a
    failed job, never as a completed job.  A repeated call with the same
    observation is a no-op at the ledger level; conflicting terminal
    observations are rejected.
    """

    plan_path = Path(plan_path).resolve()
    table_path = Path(table_path).resolve()
    plan = _read_plan(plan_path)
    job = _find_job(plan, job_key)
    resolved_job_id = _resolve_job_id(job, job_id)
    artifact = _inspect_artifact(
        job,
        artifact_dir=artifact_dir,
        job_id=resolved_job_id,
    )
    try:
        contract = _persist_runtime_contract(
            plan_path,
            job_key=job_key,
            job_id=resolved_job_id,
            source_sha=str(plan.get("source_sha") or ""),
            runtime_contract_path=runtime_contract_path,
            existing_runtime_contract_path=job.get("runtime_contract_path"),
        )
    except ValueError as exc:
        if producer_only:
            raise
        contract = {"path": "", "sha256": "", "failure_reason": str(exc)}

    if producer_only:
        return _record_producer_completion(
            plan,
            plan_path,
            table_path,
            job,
            job_key=job_key,
            job_id=resolved_job_id,
            artifact=artifact,
            contract=contract,
            producer_exit_code=producer_exit_code,
        )

    return _record_terminal_completion(
        plan,
        plan_path,
        table_path,
        job,
        job_key=job_key,
        job_id=resolved_job_id,
        artifact=artifact,
        contract=contract,
        slurm_state=slurm_state,
        slurm_exit_code=slurm_exit_code,
        producer_exit_code=producer_exit_code,
    )


def _record_terminal_completion(
    plan: dict[str, Any],
    plan_path: Path,
    table_path: Path,
    job: dict[str, Any],
    job_id: str,
    *,
    job_key: str,
    artifact: dict[str, Any],
    contract: dict[str, str],
    slurm_state: str | None,
    slurm_exit_code: str | None,
    producer_exit_code: int | None,
) -> dict[str, Any]:
    observed_state, observed_exit_code = _resolve_slurm_status(
        job_id,
        slurm_state=slurm_state,
        slurm_exit_code=slurm_exit_code,
    )
    failure_reasons = _failure_reasons(
        artifact,
        contract,
        observed_state,
        observed_exit_code,
        producer_exit_code,
    )
    failure_reasons.extend(
        producer_completion_failure_reasons(
            job,
            artifact_dir=str(artifact["artifact_dir"]),
            artifact_digest=str(artifact["artifact_digest"]),
            formal_audit_status=str(artifact["formal_audit_status"]),
            formal_audit_path=str(artifact["formal_audit_path"]),
            formal_audit_sha256=str(artifact["formal_audit_sha256"]),
            runtime_contract_path=str(contract["path"]),
            runtime_contract_sha256=str(contract["sha256"]),
        )
    )
    slurm_clean = observed_state == "COMPLETED" and observed_exit_code == "0:0"
    artifact_complete = bool(artifact["artifact_complete"]) and slurm_clean
    valid = not failure_reasons and artifact_complete
    incoming = _incoming_fields(
        job_id,
        valid,
        observed_state,
        observed_exit_code,
        artifact,
        artifact_complete,
        contract,
        failure_reasons,
    )
    _validate_replay(job, incoming)
    job.update(incoming)
    job["completion_reconciliation_contract"] = TERMINAL_RECONCILIATION_SCHEMA_VERSION
    _write_plan_and_table(plan, plan_path, table_path)

    return {
        "schema_version": TERMINAL_RECONCILIATION_SCHEMA_VERSION,
        "job_key": job_key,
        "job_id": job_id,
        "valid": valid,
        **{key: incoming[key] for key in incoming if key != "job_id"},
        "producer_exit_code": producer_exit_code,
    }


def _record_producer_completion(
    plan: dict[str, Any],
    plan_path: Path,
    table_path: Path,
    job: dict[str, Any],
    *,
    job_key: str,
    job_id: str,
    artifact: dict[str, Any],
    contract: dict[str, str],
    producer_exit_code: int | None,
) -> dict[str, Any]:
    """Persist the producer observation without inventing a Slurm terminal state."""

    failure_reasons = list(artifact["failure_reasons"])
    if producer_exit_code != 0:
        failure_reasons.append(
            "producer exit code is missing"
            if producer_exit_code is None
            else f"producer exit code={producer_exit_code}"
        )
    if contract["failure_reason"]:
        failure_reasons.append(contract["failure_reason"])
    valid = not failure_reasons and bool(artifact["artifact_complete"])
    incoming = {
        "producer_completion_state": "VERIFIED" if valid else "FAILED",
        "producer_exit_code": (
            producer_exit_code if producer_exit_code is not None else ""
        ),
        "producer_artifact_complete": bool(artifact["artifact_complete"]),
        "producer_artifact_digest": (
            str(artifact["artifact_digest"]) if artifact["artifact_complete"] else ""
        ),
        "producer_artifact_dir": str(artifact["artifact_dir"]),
        "producer_failure_reason": "; ".join(dict.fromkeys(failure_reasons)),
        "formal_audit_status": str(artifact["formal_audit_status"]),
        "formal_audit_path": str(artifact["formal_audit_path"]),
        "formal_audit_sha256": str(artifact["formal_audit_sha256"]),
        "runtime_contract_path": str(contract["path"]),
        "runtime_contract_sha256": str(contract["sha256"]),
    }
    if not valid:
        incoming["state"] = "FAILED"
        incoming["failure_reason"] = incoming["producer_failure_reason"]
    _validate_producer_replay(job, incoming)
    job.update(incoming)
    job["producer_completion_contract"] = PRODUCER_COMPLETION_SCHEMA_VERSION
    _write_plan_and_table(plan, plan_path, table_path)
    return {
        "schema_version": PRODUCER_COMPLETION_SCHEMA_VERSION,
        "job_key": job_key,
        "job_id": job_id,
        "state": incoming["producer_completion_state"],
        "valid": valid,
        **incoming,
    }


def producer_completion_failure_reasons(
    job: dict[str, Any],
    *,
    artifact_dir: str,
    artifact_digest: str,
    formal_audit_status: str,
    formal_audit_path: str,
    formal_audit_sha256: str,
    runtime_contract_path: str,
    runtime_contract_sha256: str,
) -> list[str]:
    """Cross-check the durable producer observation against terminal inputs."""

    reasons: list[str] = []
    if job.get("producer_completion_contract") != PRODUCER_COMPLETION_SCHEMA_VERSION:
        reasons.append("producer completion contract is missing")
    if job.get("producer_completion_state") != "VERIFIED":
        reasons.append(
            "producer completion is not verified: "
            f"{job.get('producer_completion_state') or 'missing'}"
        )
    if job.get("producer_exit_code") != 0:
        reasons.append(
            f"producer exit code is not clean: {job.get('producer_exit_code')!r}"
        )
    if job.get("producer_artifact_complete") is not True:
        reasons.append("producer artifact completion is not verified")
    expected = {
        "producer_artifact_digest": artifact_digest,
        "producer_artifact_dir": artifact_dir,
        "formal_audit_status": formal_audit_status,
        "runtime_contract_path": runtime_contract_path,
        "runtime_contract_sha256": runtime_contract_sha256,
    }
    if formal_audit_status != "not_present":
        expected.update(
            {
                "formal_audit_path": formal_audit_path,
                "formal_audit_sha256": formal_audit_sha256,
            }
        )
    for field, observed in expected.items():
        recorded = str(job.get(field) or "")
        if not recorded or recorded != observed:
            reasons.append(
                f"producer completion mismatch for {field}: "
                f"recorded={recorded!r} observed={observed!r}"
            )
    contract_path = Path(runtime_contract_path)
    if not contract_path.is_file():
        reasons.append(f"durable runtime contract is missing: {contract_path}")
    elif file_sha256(contract_path) != runtime_contract_sha256:
        reasons.append("durable runtime contract digest mismatch")
    return list(dict.fromkeys(reasons))


@contextmanager
def _ledger_lock(plan_path: Path):
    lock_path = plan_path.with_name(f".{plan_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _incoming_fields(
    job_id: str,
    valid: bool,
    slurm_state: str,
    slurm_exit_code: str,
    artifact: dict[str, Any],
    artifact_complete: bool,
    contract: dict[str, str],
    failure_reasons: list[str],
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "state": "COMPLETED" if valid else "FAILED",
        "slurm_state": slurm_state,
        "slurm_exit_code": slurm_exit_code,
        "exit_code": slurm_exit_code,
        "artifact_complete": artifact_complete,
        "artifact_digest": (
            str(artifact["artifact_digest"]) if artifact_complete else ""
        ),
        "artifact_dir": str(artifact["artifact_dir"]),
        "formal_audit_status": str(artifact["formal_audit_status"]),
        "formal_audit_path": str(artifact["formal_audit_path"]),
        "formal_audit_sha256": str(artifact["formal_audit_sha256"]),
        "runtime_contract_path": str(contract["path"]),
        "runtime_contract_sha256": str(contract["sha256"]),
        "failure_reason": "; ".join(dict.fromkeys(failure_reasons)),
    }


def _failure_reasons(
    artifact: dict[str, Any],
    contract: dict[str, str],
    observed_state: str,
    observed_exit_code: str,
    producer_exit_code: int | None,
) -> list[str]:
    reasons = list(artifact["failure_reasons"])
    if observed_state not in _TERMINAL_STATES:
        reasons.append(f"Slurm state is not terminal: {observed_state or 'UNKNOWN'}")
    if observed_state != "COMPLETED" or observed_exit_code != "0:0":
        reasons.append(
            "slurm state="
            f"{observed_state or 'UNKNOWN'} exit_code={observed_exit_code or '<unknown>'}"
        )
    if producer_exit_code not in (None, 0):
        reasons.append(f"producer exit code={producer_exit_code}")
    if contract["failure_reason"]:
        reasons.append(contract["failure_reason"])
    return list(dict.fromkeys(reasons))


def _validate_replay(job: dict[str, Any], incoming: dict[str, Any]) -> None:
    recorded_job_id = str(job.get("job_id") or "").strip()
    if recorded_job_id and recorded_job_id != incoming["job_id"]:
        raise ValueError(
            "job ID does not match execution plan: "
            f"recorded={recorded_job_id} incoming={incoming['job_id']}"
        )
    if str(job.get("slurm_state") or "").strip() and str(job.get("state") or "") in {
        "COMPLETED",
        "FAILED",
    }:
        for field in (
            "state",
            "slurm_state",
            "slurm_exit_code",
            "exit_code",
            "artifact_complete",
            "artifact_digest",
            "artifact_dir",
            "formal_audit_status",
            "formal_audit_path",
            "formal_audit_sha256",
            "runtime_contract_sha256",
        ):
            recorded = job.get(field)
            if recorded not in (None, "") and recorded != incoming[field]:
                raise ValueError(
                    f"completion reconciliation conflicts with durable ledger field {field}: "
                    f"recorded={recorded!r} incoming={incoming[field]!r}"
                )


def _validate_producer_replay(job: dict[str, Any], incoming: dict[str, Any]) -> None:
    if not str(job.get("producer_completion_contract") or "").strip():
        return
    for field in (
        "producer_completion_state",
        "producer_exit_code",
        "producer_artifact_complete",
        "producer_artifact_digest",
        "producer_artifact_dir",
        "producer_failure_reason",
        "formal_audit_status",
        "formal_audit_path",
        "formal_audit_sha256",
        "runtime_contract_path",
        "runtime_contract_sha256",
    ):
        if job.get(field) != incoming[field]:
            raise ValueError(
                "producer completion reconciliation conflicts with durable ledger field "
                f"{field}: recorded={job.get(field)!r} incoming={incoming[field]!r}"
            )
