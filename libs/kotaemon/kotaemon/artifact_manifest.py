from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from .artifact_identifiers import namespace_token
from .artifact_paths import portable_member_key, validate_portable_component
from .artifact_secure_fs import (
    atomic_write_bytes,
    list_regular_files,
    open_directory_fd,
    open_regular_file,
)
from .artifact_types import (
    ArtifactNamespaceError,
    FileIdentity,
    ManifestArtifact,
    digest_fd,
)

MANIFEST_VERSION = 1
ARTIFACT_KINDS = ("chunks", "markdown")
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MANIFEST_ENTRIES = 2_000
MAX_RELATIVE_PATH_LENGTH = 1_024
MAX_TOTAL_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024

EntryResolver = Callable[
    [object, str, Mapping[str, str | Path]],
    ManifestArtifact,
]


class _DuplicateJsonKey(ValueError):
    pass


def publish_artifact_manifest(
    file_id: str,
    generation: str,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
) -> Path:
    entries = _published_entries(file_id, generation, artifact_roots)
    record = {"version": MANIFEST_VERSION, "file_id": file_id, "entries": entries}
    payload = json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ArtifactNamespaceError("Artifact manifest exceeds size limit")
    return atomic_write_bytes(
        manifest_root,
        ("manifests", "v1", file_id),
        "manifest.json",
        payload,
    )


def load_manifest_artifacts(
    file_id: str,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
    *,
    resolve_entry: EntryResolver,
) -> list[ManifestArtifact]:
    record = _read_manifest(manifest_root, file_id)
    entries = _validate_manifest_record(record, file_id)
    artifacts: list[ManifestArtifact] = []
    archive_names: set[str] = set()
    total_size = 0
    try:
        for entry in entries:
            artifact = resolve_entry(entry, file_id, artifact_roots)
            key = portable_member_key(artifact.archive_name)
            if key in archive_names:
                artifact.close()
                raise ArtifactNamespaceError("Duplicate artifact archive name")
            archive_names.add(key)
            total_size += artifact.size
            if total_size > MAX_TOTAL_ARTIFACT_BYTES:
                artifact.close()
                raise ArtifactNamespaceError("Artifact total size exceeds limit")
            artifacts.append(artifact)
        return artifacts
    except BaseException:
        close_manifest_artifacts(artifacts)
        raise


def resolve_manifest_entry(
    entry: object,
    file_id: str,
    artifact_roots: Mapping[str, str | Path],
) -> ManifestArtifact:
    if not isinstance(entry, dict) or set(entry) != {"kind", "relative_path"}:
        raise ArtifactNamespaceError("Invalid artifact manifest entry")
    kind = entry["kind"]
    if not isinstance(kind, str) or kind not in ARTIFACT_KINDS:
        raise ArtifactNamespaceError("Invalid artifact kind")
    if kind not in artifact_roots:
        raise ArtifactNamespaceError(f"Missing artifact root: {kind}")
    parts = relative_parts(entry["relative_path"])
    if len(parts) != 3 or parts[0] != file_id:
        raise ArtifactNamespaceError("Invalid artifact relative path layout")
    if namespace_token(parts[1]) != parts[1]:
        raise ArtifactNamespaceError("Invalid artifact generation")
    fd, metadata = open_regular_file(artifact_roots[kind], parts)
    try:
        if metadata.st_size > MAX_TOTAL_ARTIFACT_BYTES:
            raise ArtifactNamespaceError("Artifact total size exceeds limit")
        archive_name = PurePosixPath(kind, *parts[2:]).as_posix()
        identity = FileIdentity.from_stat(metadata)
        digest = digest_fd(fd, metadata.st_size)
        identity.validate_fd(fd, message="Artifact changed while validating")
        return ManifestArtifact(
            fd=fd,
            archive_name=archive_name,
            size=metadata.st_size,
            identity=identity,
            digest=digest,
        )
    except BaseException:
        os.close(fd)
        raise


def relative_parts(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_RELATIVE_PATH_LENGTH
        or "\\" in value
        or "\x00" in value
        or value.startswith("/")
    ):
        raise ArtifactNamespaceError("Invalid artifact relative path")
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ArtifactNamespaceError("Invalid artifact relative path")
    try:
        for part in parts:
            validate_portable_component(part)
    except ArtifactNamespaceError as exc:
        raise ArtifactNamespaceError("Invalid artifact relative path") from exc
    return parts


def close_manifest_artifacts(artifacts: list[ManifestArtifact]) -> None:
    for artifact in artifacts:
        try:
            artifact.close()
        except OSError:
            pass


def _published_entries(
    file_id: str,
    generation: str,
    artifact_roots: Mapping[str, str | Path],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    total_size = 0
    for kind in ARTIFACT_KINDS:
        if kind not in artifact_roots:
            raise ArtifactNamespaceError(f"Missing artifact root: {kind}")
        _ensure_root(artifact_roots[kind])
        for name, metadata in list_regular_files(
            artifact_roots[kind],
            (file_id, generation),
        ):
            total_size += metadata.st_size
            if total_size > MAX_TOTAL_ARTIFACT_BYTES:
                raise ArtifactNamespaceError("Artifact total size exceeds limit")
            entries.append(
                {
                    "kind": kind,
                    "relative_path": f"{file_id}/{generation}/{name}",
                }
            )
            if len(entries) > MAX_MANIFEST_ENTRIES:
                raise ArtifactNamespaceError("Artifact manifest has too many entries")
    return entries


def _ensure_root(root: str | Path) -> None:
    _path, fd = open_directory_fd(root, create=True)
    os.close(fd)


def _read_manifest(manifest_root: str | Path, file_id: str) -> dict[str, Any]:
    fd = -1
    try:
        fd, metadata = open_regular_file(
            manifest_root,
            ("manifests", "v1", file_id, "manifest.json"),
        )
        if metadata.st_size > MAX_MANIFEST_BYTES:
            raise ArtifactNamespaceError("Artifact manifest exceeds size limit")
        identity = FileIdentity.from_stat(metadata)
        payload = _read_bounded(fd)
        identity.validate_fd(fd, message="Artifact manifest changed while reading")
        if os.pread(fd, len(payload) + 1, 0) != payload:
            raise ArtifactNamespaceError("Artifact manifest changed while reading")
        record = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except _DuplicateJsonKey as exc:
        raise ArtifactNamespaceError(
            "Artifact manifest contains duplicate keys"
        ) from exc
    except ArtifactNamespaceError:
        raise
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
    ) as exc:
        raise ArtifactNamespaceError("Artifact manifest unavailable") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(record, dict):
        raise ArtifactNamespaceError("Artifact manifest must be an object")
    return record


def _read_bounded(fd: int) -> bytes:
    chunks = []
    remaining = MAX_MANIFEST_BYTES + 1
    while remaining:
        chunk = os.read(fd, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ArtifactNamespaceError("Artifact manifest exceeds size limit")
    return payload


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _validate_manifest_record(record: dict[str, Any], file_id: str) -> list[Any]:
    if set(record) != {"version", "file_id", "entries"}:
        raise ArtifactNamespaceError("Invalid artifact manifest fields")
    version = record["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ArtifactNamespaceError("Invalid artifact manifest version")
    if version != MANIFEST_VERSION or record["file_id"] != file_id:
        raise ArtifactNamespaceError("Artifact manifest identity mismatch")
    entries = record["entries"]
    if not isinstance(entries, list) or not entries:
        raise ArtifactNamespaceError(
            "Artifact manifest entries must be a nonempty list"
        )
    if len(entries) > MAX_MANIFEST_ENTRIES:
        raise ArtifactNamespaceError("Artifact manifest has too many entries")
    return entries


__all__ = [
    "ARTIFACT_KINDS",
    "MANIFEST_VERSION",
    "close_manifest_artifacts",
    "load_manifest_artifacts",
    "publish_artifact_manifest",
    "relative_parts",
    "resolve_manifest_entry",
]
