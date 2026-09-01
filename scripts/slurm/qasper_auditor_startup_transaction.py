from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

CONTRACT_ID = "qasper_auditor_startup_transaction.v1"
SCRIPT_IDENTITY_CONTRACT_ID = "qasper_submission_script_identity.v1"
_CACHE_ENVIRONMENT = (
    "VLLM_WORKER_MULTIPROC_METHOD",
    "FLASHINFER_WORKSPACE_BASE",
    "FLASHINFER_CUBIN_DIR",
    "TRITON_CACHE_DIR",
    "CUDA_CACHE_PATH",
)
_RUNTIME_ARTIFACT_NAMES = (
    "modules.txt",
    "cuda_toolchain.txt",
    "provider_toolchain.txt",
    "provider_python_stack.txt",
    "auditor_provider.log",
)


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate_source_sha(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise ValueError("source_sha must be a full 40-character Git SHA")
    return normalized


def write_submission_script_identity(
    script_path: str | Path,
    *,
    project_root: str | Path,
    source_sha: str,
    output_path: str | Path,
    checksum_path: str | Path,
) -> dict[str, Any]:
    script = Path(script_path).resolve(strict=True)
    root = Path(project_root).resolve(strict=True)
    try:
        relative = script.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "submission script must use a stable path inside the checkout"
        ) from exc
    digest = _file_sha256(script)
    identity = {
        "contract_id": SCRIPT_IDENTITY_CONTRACT_ID,
        "source_sha": _validate_source_sha(source_sha),
        "project_root": str(root),
        "stable_path": str(script),
        "relative_path": relative.as_posix(),
        "sha256": digest,
    }
    identity["identity_digest"] = _canonical_digest(identity)
    _atomic_write_json(Path(output_path), identity)
    _atomic_write_text(Path(checksum_path), f"{digest}  {script}\n")
    return identity


def _startup_identity(
    script_identity: Mapping[str, Any], environment: Mapping[str, str]
) -> dict[str, Any]:
    source_sha = _validate_source_sha(environment.get("MARA_EXPECTED_SHA", ""))
    if script_identity.get("source_sha") != source_sha:
        raise ValueError("submission script and startup source SHA disagree")
    return {
        "source_sha": source_sha,
        "worktree_path": str(Path(environment["MARA_PROJECT_ROOT"]).resolve()),
        "slurm_job_id": environment.get("SLURM_JOB_ID", ""),
        "node": environment.get("SLURMD_NODENAME", ""),
        "run_mode": environment.get("MARA_AUDITOR_RUN_MODE", ""),
        "auditor": {
            "model": environment.get("MARA_QASPER_CONTRACT_AUDITOR_MODEL", ""),
            "base_url": environment.get("MARA_QASPER_CONTRACT_AUDITOR_BASE_URL", ""),
            "vllm_binary": environment.get("VLLM_BIN", ""),
            "vllm_python": environment.get("VLLM_PYTHON", ""),
        },
        "runtime": {
            "cache_environment": {
                name: environment.get(name, "") for name in _CACHE_ENVIRONMENT
            },
        },
        "submission_script": dict(script_identity),
    }


def _transport_status(status: str, failed_before_transport: bool | None) -> str:
    if status == "ready":
        return "provider_ready"
    if status == "failed" and failed_before_transport is True:
        return "failed_before_transport"
    return "not_started"


def _startup_models_artifact(
    models_artifact_path: str | Path | None,
) -> dict[str, Any]:
    if models_artifact_path is None:
        return {}
    models_path = Path(models_artifact_path).resolve(strict=True)
    return {"path": str(models_path), "sha256": _file_sha256(models_path)}


def _startup_runtime_artifacts(environment: Mapping[str, str]) -> dict[str, Any]:
    root_value = environment.get("MARA_TEXT_RUN_ROOT", "")
    if not root_value:
        return {}
    root = Path(root_value).resolve()
    return {
        name: {"path": str(path), "sha256": _file_sha256(path)}
        for name in _RUNTIME_ARTIFACT_NAMES
        if (path := root / name).is_file()
    }


def record_auditor_startup_event(
    output_path: str | Path,
    *,
    script_identity_path: str | Path,
    status: str,
    phase: str,
    failed_before_transport: bool | None = None,
    exit_code: int | None = None,
    failure_message: str = "",
    models_artifact_path: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if status not in {"starting", "ready", "failed"}:
        raise ValueError(f"unsupported auditor startup status: {status}")
    if status == "failed" and failed_before_transport is not True:
        raise ValueError(
            "failed auditor startup must be marked failed_before_transport"
        )
    env = os.environ if environment is None else environment
    script_identity = _read_object(Path(script_identity_path))
    identity = _startup_identity(script_identity, env)
    identity_digest = _canonical_digest(identity)
    destination = Path(output_path)
    existing = _read_object(destination) if destination.exists() else {}
    events = list(existing.get("events") or [])
    if existing:
        if existing.get("contract_id") != CONTRACT_ID:
            raise ValueError("auditor startup transaction contract mismatch")
        if existing.get("identity_digest") != identity_digest:
            raise ValueError("auditor startup transaction identity changed")
        if existing.get("status") in {"ready", "failed"}:
            raise ValueError("auditor startup transaction is already terminal")
    previous_digest = str(events[-1].get("event_digest") or "") if events else ""
    event = {
        "sequence": len(events) + 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "phase": phase,
        "transport_status": _transport_status(status, failed_before_transport),
        "failed_before_transport": failed_before_transport,
        "exit_code": exit_code,
        "failure_message": failure_message,
        "models_artifact": _startup_models_artifact(models_artifact_path),
        "runtime_artifacts": _startup_runtime_artifacts(env),
        "runtime_snapshot": {"cuda_home": env.get("CUDA_HOME", "")},
        "previous_event_digest": previous_digest,
    }
    event["event_digest"] = _canonical_digest(event)
    events.append(event)
    failure = (
        {"exit_code": exit_code, "message": failure_message}
        if status == "failed"
        else {}
    )
    transaction = {
        "contract_id": CONTRACT_ID,
        "transaction_id": _canonical_digest(
            {
                "identity_digest": identity_digest,
                "slurm_job_id": identity["slurm_job_id"],
            }
        ),
        "identity": identity,
        "identity_digest": identity_digest,
        "status": status,
        "phase": phase,
        "transport_status": event["transport_status"],
        "failed_before_transport": failed_before_transport,
        "failure": failure,
        "events": events,
        "event_chain_digest": event["event_digest"],
    }
    transaction["transaction_digest"] = _canonical_digest(transaction)
    _atomic_write_json(destination, transaction)
    return transaction


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    identity = commands.add_parser("script-identity")
    identity.add_argument("--script", type=Path, required=True)
    identity.add_argument("--project-root", type=Path, required=True)
    identity.add_argument("--source-sha", required=True)
    identity.add_argument("--output", type=Path, required=True)
    identity.add_argument("--checksum-output", type=Path, required=True)
    record = commands.add_parser("record")
    record.add_argument("--output", type=Path, required=True)
    record.add_argument("--script-identity", type=Path, required=True)
    record.add_argument(
        "--status", choices=("starting", "ready", "failed"), required=True
    )
    record.add_argument("--phase", required=True)
    record.add_argument("--failed-before-transport", action="store_true")
    record.add_argument("--exit-code", type=int)
    record.add_argument("--failure-message", default="")
    record.add_argument("--models-artifact", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "script-identity":
        write_submission_script_identity(
            args.script,
            project_root=args.project_root,
            source_sha=args.source_sha,
            output_path=args.output,
            checksum_path=args.checksum_output,
        )
    else:
        record_auditor_startup_event(
            args.output,
            script_identity_path=args.script_identity,
            status=args.status,
            phase=args.phase,
            failed_before_transport=args.failed_before_transport or None,
            exit_code=args.exit_code,
            failure_message=args.failure_message,
            models_artifact_path=args.models_artifact,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
