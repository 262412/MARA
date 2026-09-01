from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ARTIFACT_MANIFEST_NAME = "artifact_manifest.json"
ARTIFACT_COMPLETE_NAME = "artifact_complete.json"
ARTIFACT_CONTRACT_VERSION = "benchmark_artifact.v1"
_PRIMARY_ARTIFACTS = (
    "summary.json",
    "predictions.jsonl",
    "documents.json",
    "retrieval_traces.jsonl",
    "semantic_debug_traces.jsonl",
    "report.md",
    "route_metrics.csv",
    "contract_probe_predictions.jsonl",
    "contract_pre_audit_predictions.jsonl",
    "contract_probe_audit.json",
    "retrieval_index_artifact.json",
    "retrieval_index_restore_audit.json",
    "contract_smoke_audit.json",
)

_ARTIFACT_REQUIREMENT_ALIASES = {
    "semantic_trace": "semantic_debug_traces.jsonl",
    "semantic_traces": "semantic_debug_traces.jsonl",
    "semantic_debug_trace": "semantic_debug_traces.jsonl",
    "semantic_debug_traces": "semantic_debug_traces.jsonl",
    "semantic_debug_trace_jsonl": "semantic_debug_traces.jsonl",
    "semantic_debug_traces_jsonl": "semantic_debug_traces.jsonl",
    "require_semantic_debug_trace": "semantic_debug_traces.jsonl",
    "require_semantic_debug_traces": "semantic_debug_traces.jsonl",
    "formal_audit": "contract_smoke_audit.json",
    "contract_audit": "contract_smoke_audit.json",
    "contract_smoke_audit": "contract_smoke_audit.json",
    "contract_smoke_audit_json": "contract_smoke_audit.json",
    "require_formal_audit": "contract_smoke_audit.json",
    "require_contract_smoke_audit": "contract_smoke_audit.json",
    "require_contract_smoke": "contract_smoke_audit.json",
    "retrieval_index_artifact": "retrieval_index_artifact.json",
    "retrieval_index_restore_audit": "retrieval_index_restore_audit.json",
}


def atomic_write_bytes(path: str | Path, payload: bytes) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        _fsync_directory(destination.parent)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def atomic_write_text(path: str | Path, text: str) -> None:
    atomic_write_bytes(Path(path), text.encode("utf-8"))


def atomic_write_json(path: str | Path, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def atomic_write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        _fsync_directory(destination.parent)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def publish_artifact_contract(
    run_dir: str | Path,
    *,
    run_requirements: Any = None,
) -> dict[str, Any]:
    """Publish a digest manifest and completion marker for a benchmark run.

    Required artifacts come from the run requirements as well as files already
    present.  This keeps a missing required artifact from being silently
    reclassified as optional during publication.
    """

    run_dir = Path(run_dir).resolve()
    existing_manifest = _existing_manifest(run_dir / ARTIFACT_MANIFEST_NAME)
    required_from_manifest = normalize_artifact_requirements(
        existing_manifest.get("required_files")
    )
    required_from_run = normalize_artifact_requirements(run_requirements)
    declared_requirements = normalize_artifact_requirements(
        existing_manifest.get("run_requirements")
    )
    declared_requirements = _ordered_unique(
        [*declared_requirements, *required_from_run]
    )
    files: dict[str, dict[str, Any]] = {}
    for name in _PRIMARY_ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            continue
        metadata: dict[str, Any] = {
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        if path.suffix == ".jsonl":
            metadata["line_count"] = _physical_lf_count(path)
        files[name] = metadata

    required = [
        name
        for name in _PRIMARY_ARTIFACTS
        if name in files or name in required_from_manifest or name in required_from_run
    ]
    missing_required_files = [name for name in required if name not in files]
    required_file_failures = _required_file_failures(run_dir, required, files)
    missing_required_files = _ordered_unique(
        [*missing_required_files, *required_file_failures]
    )
    manifest = {
        "contract": ARTIFACT_CONTRACT_VERSION,
        "required_files": required,
        "files": files,
        "run_requirements": declared_requirements,
        "missing_required_files": missing_required_files,
        "required_file_failures": required_file_failures,
    }
    manifest_path = run_dir / ARTIFACT_MANIFEST_NAME
    atomic_write_json(manifest_path, manifest)
    marker = {
        "contract": ARTIFACT_CONTRACT_VERSION,
        "complete": not missing_required_files,
        "artifact_manifest": ARTIFACT_MANIFEST_NAME,
        "artifact_manifest_sha256": file_sha256(manifest_path),
        "required_files": required,
        "missing_required_files": missing_required_files,
        "required_file_failures": required_file_failures,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(run_dir / ARTIFACT_COMPLETE_NAME, marker)
    return marker


def publish_contract_smoke_audit(
    run_dir: str | Path,
    audit: dict[str, Any],
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    atomic_write_json(run_dir / "contract_smoke_audit.json", audit)
    requirements: dict[str, bool] = {"contract_smoke_audit": True}
    if str(audit.get("suite_kind") or "").strip().casefold() == "qasper_debug":
        requirements["semantic_debug_traces"] = True
        requirements["retrieval_index_artifact"] = True
        requirements["retrieval_index_restore_audit"] = True
    return publish_artifact_contract(
        run_dir,
        run_requirements=requirements,
    )


def normalize_artifact_requirements(value: Any) -> list[str]:
    """Normalize run requirement declarations to known artifact file names."""

    names: list[str] = []
    if isinstance(value, Mapping):
        for key, enabled in value.items():
            key_text = str(key).strip().casefold()
            if key_text in {"required_files", "required_artifacts", "artifacts"}:
                if _requirement_enabled(enabled):
                    names.extend(normalize_artifact_requirements(enabled))
                continue
            if not _requirement_enabled(enabled):
                continue
            name = _normalize_artifact_name(key_text)
            if name:
                names.append(name)
    elif isinstance(value, str):
        name = _normalize_artifact_name(value)
        if name:
            names.append(name)
    elif isinstance(value, Iterable):
        for item in value:
            names.extend(normalize_artifact_requirements(item))
    return _ordered_unique(names)


def _normalize_artifact_name(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return ""
    if normalized in _ARTIFACT_REQUIREMENT_ALIASES:
        return _ARTIFACT_REQUIREMENT_ALIASES[normalized]
    if normalized in {name.casefold() for name in _PRIMARY_ARTIFACTS}:
        return next(
            name for name in _PRIMARY_ARTIFACTS if name.casefold() == normalized
        )
    return ""


def _requirement_enabled(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value.get("required", value.get("enabled", False)))
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _existing_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _required_file_failures(
    run_dir: Path,
    required: list[str],
    files: Mapping[str, dict[str, Any]],
) -> list[str]:
    semantic_name = "semantic_debug_traces.jsonl"
    predictions_path = run_dir / "predictions.jsonl"
    semantic_path = run_dir / semantic_name
    if (
        semantic_name not in required
        or semantic_name not in files
        or not predictions_path.is_file()
        or not semantic_path.is_file()
    ):
        return []
    expected = _nonempty_line_count(predictions_path)
    if expected <= 0:
        return []
    actual = _nonempty_line_count(semantic_path)
    if actual == expected:
        return []
    return [semantic_name]


def verify_artifact_contract(run_dir: str | Path) -> dict[str, Any]:
    """Fail closed unless the marker and every published digest still match."""

    run_dir = Path(run_dir).resolve()
    marker_path = run_dir / ARTIFACT_COMPLETE_NAME
    manifest_path = run_dir / ARTIFACT_MANIFEST_NAME
    marker = _read_object(marker_path)
    if marker.get("contract") != ARTIFACT_CONTRACT_VERSION:
        raise ValueError(f"unsupported artifact contract in {marker_path}")
    if marker.get("complete") is not True:
        raise ValueError(f"artifact completion marker is not complete: {marker_path}")
    if marker.get("artifact_manifest") != ARTIFACT_MANIFEST_NAME:
        raise ValueError(
            f"artifact marker points to an unexpected manifest: {marker_path}"
        )
    if marker.get("artifact_manifest_sha256") != file_sha256(manifest_path):
        raise ValueError(
            f"artifact manifest digest changed after publication: {run_dir}"
        )

    manifest = _read_object(manifest_path)
    if manifest.get("contract") != ARTIFACT_CONTRACT_VERSION:
        raise ValueError(f"unsupported artifact manifest contract in {manifest_path}")
    files = manifest.get("files")
    required = manifest.get("required_files")
    if not isinstance(files, dict) or not isinstance(required, list):
        raise ValueError(f"artifact manifest is missing file metadata: {manifest_path}")
    unexpected = [
        name
        for name in _PRIMARY_ARTIFACTS
        if (run_dir / name).is_file() and name not in required
    ]
    if unexpected:
        raise ValueError(f"artifact publication omitted existing files: {unexpected}")
    for name in required:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError(
                f"artifact manifest contains an unsafe file name: {name!r}"
            )
        metadata = files.get(name)
        path = run_dir / name
        if not isinstance(metadata, dict) or not path.is_file():
            raise ValueError(f"published artifact is missing: {path}")
        if metadata.get("sha256") != file_sha256(path):
            raise ValueError(f"published artifact digest changed: {path}")
        if metadata.get("size_bytes") != path.stat().st_size:
            raise ValueError(f"published artifact size changed: {path}")
    return marker


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _physical_lf_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(
            block.count(b"\n") for block in iter(lambda: handle.read(1024 * 1024), b"")
        )


def _nonempty_line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            f"required artifact publication file is missing: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError(f"artifact publication file must contain an object: {path}")
    return value


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
