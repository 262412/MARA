from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .artifact_identifiers import namespace_token
from .artifact_manifest import ARTIFACT_KINDS, MANIFEST_VERSION
from .artifact_manifest import load_manifest_artifacts as _load_manifest_artifacts
from .artifact_manifest import publish_artifact_manifest as _publish_artifact_manifest
from .artifact_manifest import resolve_manifest_entry
from .artifact_pipeline import finish_indexing
from .artifact_producers import (
    artifact_output_path,
    write_chunk_artifacts,
    write_markdown_artifact,
)
from .artifact_secure_fs import open_directory_fd
from .artifact_types import ArtifactNamespaceError, ManifestArtifact


def manifest_path(
    manifest_root: str | Path,
    file_id: object,
    *,
    create: bool = False,
) -> Path:
    token = namespace_token(file_id)
    path, fd = open_directory_fd(
        manifest_root,
        ("manifests", "v1", token),
        create=create,
    )
    os.close(fd)
    return path / "manifest.json"


def publish_artifact_manifest(
    file_id: object,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
    *,
    artifact_generation: object,
) -> Path:
    token = namespace_token(file_id)
    generation = namespace_token(artifact_generation)
    return _publish_artifact_manifest(
        token,
        generation,
        artifact_roots,
        manifest_root,
    )


def publish_runtime_manifest(
    file_id: object,
    settings: Any,
    *,
    artifact_generation: object,
) -> Path:
    return publish_artifact_manifest(
        file_id,
        {
            "chunks": settings.KH_CHUNKS_OUTPUT_DIR,
            "markdown": settings.KH_MARKDOWN_OUTPUT_DIR,
        },
        settings.KH_ZIP_OUTPUT_DIR,
        artifact_generation=artifact_generation,
    )


def finish_and_publish_artifacts(
    pipeline: Any,
    file_id: object,
    source_path: str | Path,
    settings: Any,
) -> Path:
    generation = namespace_token(getattr(pipeline, "_artifact_generation", None))
    finish_indexing(pipeline, file_id, source_path)
    return publish_runtime_manifest(
        file_id,
        settings,
        artifact_generation=generation,
    )


def load_manifest_artifacts(
    file_id: object,
    artifact_roots: Mapping[str, str | Path],
    manifest_root: str | Path,
) -> list[ManifestArtifact]:
    token = namespace_token(file_id)
    return _load_manifest_artifacts(
        token,
        artifact_roots,
        manifest_root,
        resolve_entry=_resolve_manifest_entry,
    )


def _resolve_manifest_entry(
    entry: object,
    file_id: str,
    artifact_roots: Mapping[str, str | Path],
) -> ManifestArtifact:
    return resolve_manifest_entry(entry, file_id, artifact_roots)


__all__ = [
    "ARTIFACT_KINDS",
    "MANIFEST_VERSION",
    "ArtifactNamespaceError",
    "ManifestArtifact",
    "artifact_output_path",
    "finish_and_publish_artifacts",
    "load_manifest_artifacts",
    "manifest_path",
    "namespace_token",
    "publish_artifact_manifest",
    "publish_runtime_manifest",
    "write_chunk_artifacts",
    "write_markdown_artifact",
]
