from __future__ import annotations

import hashlib
import json
import os
import tempfile
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
    "report.md",
    "route_metrics.csv",
)


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


def publish_artifact_contract(run_dir: str | Path) -> dict[str, Any]:
    """Publish a digest manifest and completion marker after all artifacts exist."""

    run_dir = Path(run_dir).resolve()
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

    required = [name for name in _PRIMARY_ARTIFACTS if name in files]
    manifest = {
        "contract": ARTIFACT_CONTRACT_VERSION,
        "required_files": required,
        "files": files,
    }
    manifest_path = run_dir / ARTIFACT_MANIFEST_NAME
    atomic_write_json(manifest_path, manifest)
    marker = {
        "contract": ARTIFACT_CONTRACT_VERSION,
        "complete": True,
        "artifact_manifest": ARTIFACT_MANIFEST_NAME,
        "artifact_manifest_sha256": file_sha256(manifest_path),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(run_dir / ARTIFACT_COMPLETE_NAME, marker)
    return marker


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
        raise ValueError(f"artifact marker points to an unexpected manifest: {marker_path}")
    if marker.get("artifact_manifest_sha256") != file_sha256(manifest_path):
        raise ValueError(f"artifact manifest digest changed after publication: {run_dir}")

    manifest = _read_object(manifest_path)
    if manifest.get("contract") != ARTIFACT_CONTRACT_VERSION:
        raise ValueError(f"unsupported artifact manifest contract in {manifest_path}")
    files = manifest.get("files")
    required = manifest.get("required_files")
    if not isinstance(files, dict) or not isinstance(required, list):
        raise ValueError(f"artifact manifest is missing file metadata: {manifest_path}")
    unexpected = [
        name for name in _PRIMARY_ARTIFACTS if (run_dir / name).is_file() and name not in required
    ]
    if unexpected:
        raise ValueError(f"artifact publication omitted existing files: {unexpected}")
    for name in required:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError(f"artifact manifest contains an unsafe file name: {name!r}")
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
        return sum(block.count(b"\n") for block in iter(lambda: handle.read(1024 * 1024), b""))


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"required artifact publication file is missing: {path}") from exc
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
