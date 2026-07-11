from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence
from uuid import uuid4

MANIFEST_VERSION = 1
ARTIFACT_KINDS = ("chunks", "markdown")
_FILE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")


class ArtifactNamespaceError(ValueError):
    """Raised when an artifact namespace or manifest is unsafe."""


@dataclass(frozen=True)
class ManifestArtifact:
    path: Path
    archive_name: str


def namespace_token(file_id: object) -> str:
    token = str(file_id or "")
    if token in {".", ".."} or _FILE_ID_PATTERN.fullmatch(token) is None:
        raise ArtifactNamespaceError("Invalid artifact file identifier")
    return token


def artifact_output_path(
    root: str | Path,
    file_id: object,
    file_name: str,
) -> Path:
    output_name = _safe_file_name(file_name)
    namespace = _namespace_directory(root, file_id, create=True)
    return namespace / output_name


def write_chunk_artifacts(
    root: str | Path,
    docs: Sequence[Any],
    start_index: int,
) -> None:
    file_name = docs[0].metadata.get("file_name")
    file_id = docs[0].metadata.get("file_id")
    if not file_name or not file_id:
        return
    if any(doc.metadata.get("file_id") != file_id for doc in docs):
        raise ArtifactNamespaceError("Chunk batch contains multiple file identifiers")
    file_stem = Path(file_name).stem
    for offset, doc in enumerate(docs):
        output_path = artifact_output_path(
            root,
            file_id,
            f"{file_stem}_{start_index + offset}.md",
        )
        output_path.write_text(_chunk_markdown(doc), encoding="utf-8")


def write_markdown_artifact(
    root: str | Path | None,
    source_file: str | Path,
    metadata: Mapping[str, Any],
    content: str,
) -> None:
    file_id = metadata.get("file_id")
    if root is None or not file_id:
        return
    output_path = artifact_output_path(
        root,
        file_id,
        f"{Path(source_file).stem}.md",
    )
    output_path.write_text(content, encoding="utf-8")


def manifest_path(
    manifest_root: str | Path,
    file_id: object,
    *,
    create: bool = False,
) -> Path:
    token = namespace_token(file_id)
    root = _root_directory(manifest_root, create=create)
    directory = _directory_chain(root, ("manifests", "v1", token), create=create)
    return directory / "manifest.json"


def publish_artifact_manifest(
    file_id: object,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
) -> Path:
    token = namespace_token(file_id)
    entries = _published_entries(token, artifact_roots)
    record = {"version": MANIFEST_VERSION, "file_id": token, "entries": entries}
    target = manifest_path(manifest_root, token, create=True)
    temporary = target.with_name(f".manifest-{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(record, output, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def publish_runtime_manifest(file_id: object, settings: Any) -> Path:
    return publish_artifact_manifest(
        file_id,
        {
            "chunks": settings.KH_CHUNKS_OUTPUT_DIR,
            "markdown": settings.KH_MARKDOWN_OUTPUT_DIR,
        },
        settings.KH_ZIP_OUTPUT_DIR,
    )


def finish_and_publish_artifacts(
    pipeline: Any,
    file_id: object,
    source_path: str | Path,
    settings: Any,
) -> Path:
    pipeline.finish(file_id, source_path)
    return publish_runtime_manifest(file_id, settings)


def load_manifest_artifacts(
    file_id: object,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
) -> list[ManifestArtifact]:
    token = namespace_token(file_id)
    record = _read_manifest(manifest_root, token)
    _validate_manifest_record(record, token)
    artifacts = []
    archive_names = set()
    for entry in record["entries"]:
        artifact = _resolve_manifest_entry(entry, token, artifact_roots)
        if artifact.archive_name in archive_names:
            raise ArtifactNamespaceError("Duplicate artifact archive name")
        archive_names.add(artifact.archive_name)
        artifacts.append(artifact)
    return artifacts


def isolated_output_path(
    output_root: str | Path,
    file_id: object,
    suffix: str,
) -> Path:
    if not suffix.startswith(".") or _safe_file_name(f"download{suffix}") != (
        f"download{suffix}"
    ):
        raise ArtifactNamespaceError("Invalid download suffix")
    token = namespace_token(file_id)
    request_token = uuid4().hex
    root = _root_directory(output_root, create=True)
    directory = _directory_chain(
        root,
        ("downloads", token, request_token),
        create=True,
    )
    return directory / f"download-{request_token}{suffix}"


def _published_entries(
    file_id: str,
    artifact_roots: Mapping[str, str | Path],
) -> list[dict[str, str]]:
    entries = []
    for kind in ARTIFACT_KINDS:
        if kind not in artifact_roots:
            raise ArtifactNamespaceError(f"Missing artifact root: {kind}")
        root = _root_directory(artifact_roots[kind], create=True)
        namespace = _namespace_directory(root, file_id, create=False)
        if not namespace.exists():
            continue
        for path in sorted(namespace.rglob("*")):
            if path.is_symlink():
                raise ArtifactNamespaceError("Artifact symlinks are not allowed")
            if path.is_dir():
                continue
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ArtifactNamespaceError("Artifact must be a regular file")
            entries.append(
                {
                    "kind": kind,
                    "relative_path": path.relative_to(root).as_posix(),
                }
            )
    return entries


def _chunk_markdown(doc: Any) -> str:
    content = ""
    if "page_label" in doc.metadata:
        content += f"Page label: {doc.metadata['page_label']}"
    if "file_name" in doc.metadata:
        content += f"\nFile name: {doc.metadata['file_name']}"
    if "section" in doc.metadata:
        content += f"\nSection: {doc.metadata['section']}"
    if doc.metadata.get("type") == "image":
        image_origin = f'<p><img src="{doc.metadata["image_origin"]}"></p>'
        content += f"\nImage origin: {image_origin}"
    if doc.text:
        content += f"\ntext:\n{doc.text}"
    return content


def _read_manifest(manifest_root: str | Path, file_id: str) -> dict:
    try:
        path = manifest_path(manifest_root, file_id)
        _require_regular_file(path, path.parent.parent.parent.parent)
        with path.open(encoding="utf-8") as source:
            record = json.load(source)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ArtifactNamespaceError("Artifact manifest unavailable") from exc
    if not isinstance(record, dict):
        raise ArtifactNamespaceError("Artifact manifest must be an object")
    return record


def _validate_manifest_record(record: dict, file_id: str) -> None:
    if set(record) != {"version", "file_id", "entries"}:
        raise ArtifactNamespaceError("Invalid artifact manifest fields")
    if record["version"] != MANIFEST_VERSION or record["file_id"] != file_id:
        raise ArtifactNamespaceError("Artifact manifest identity mismatch")
    if not isinstance(record["entries"], list):
        raise ArtifactNamespaceError("Artifact manifest entries must be a list")


def _resolve_manifest_entry(
    entry: object,
    file_id: str,
    artifact_roots: Mapping[str, str | Path],
) -> ManifestArtifact:
    if not isinstance(entry, dict) or set(entry) != {"kind", "relative_path"}:
        raise ArtifactNamespaceError("Invalid artifact manifest entry")
    kind = entry["kind"]
    relative_path = entry["relative_path"]
    if kind not in ARTIFACT_KINDS or kind not in artifact_roots:
        raise ArtifactNamespaceError("Invalid artifact kind")
    parts = _relative_parts(relative_path)
    if len(parts) < 2 or parts[0] != file_id:
        raise ArtifactNamespaceError("Artifact is outside its file namespace")
    root = _root_directory(artifact_roots[kind], create=False)
    namespace = _namespace_directory(root, file_id, create=False)
    path = root.joinpath(*parts)
    _require_regular_file(path, root)
    if not path.resolve().is_relative_to(namespace.resolve()):
        raise ArtifactNamespaceError("Artifact escaped its file namespace")
    archive_name = PurePosixPath(kind, *parts[1:]).as_posix()
    return ManifestArtifact(path=path, archive_name=archive_name)


def _relative_parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ArtifactNamespaceError("Invalid artifact relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactNamespaceError("Invalid artifact relative path")
    return path.parts


def _require_regular_file(path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ArtifactNamespaceError("Artifact escaped its configured root") from exc
    current = root
    try:
        for part in relative.parts:
            current = current / part
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ArtifactNamespaceError("Artifact symlinks are not allowed")
    except FileNotFoundError as exc:
        raise ArtifactNamespaceError("Artifact file unavailable") from exc
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ArtifactNamespaceError("Artifact must be a regular file")


def _namespace_directory(
    root: str | Path,
    file_id: object,
    *,
    create: bool,
) -> Path:
    token = namespace_token(file_id)
    root_path = _root_directory(root, create=create)
    return _directory_chain(root_path, (token,), create=create)


def _root_directory(root: str | Path, *, create: bool) -> Path:
    path = Path(root).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ArtifactNamespaceError("Artifact root unavailable") from exc
    if not resolved.is_dir():
        raise ArtifactNamespaceError("Artifact root must be a directory")
    return resolved


def _directory_chain(root: Path, parts: tuple[str, ...], *, create: bool) -> Path:
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactNamespaceError("Artifact directory symlinks are not allowed")
        if create:
            current.mkdir(exist_ok=True)
        if current.exists() and not current.is_dir():
            raise ArtifactNamespaceError("Artifact namespace must be a directory")
    return current


def _safe_file_name(file_name: str) -> str:
    value = str(file_name or "")
    if (
        not value
        or value in {".", ".."}
        or "\\" in value
        or Path(value).name != value
    ):
        raise ArtifactNamespaceError("Invalid artifact output name")
    return value


__all__ = [
    "ARTIFACT_KINDS",
    "MANIFEST_VERSION",
    "ArtifactNamespaceError",
    "ManifestArtifact",
    "artifact_output_path",
    "finish_and_publish_artifacts",
    "isolated_output_path",
    "load_manifest_artifacts",
    "manifest_path",
    "namespace_token",
    "publish_artifact_manifest",
    "publish_runtime_manifest",
    "write_chunk_artifacts",
    "write_markdown_artifact",
]
