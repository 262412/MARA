"""Fail-closed cleanup for file-id-scoped generated artifacts."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Any

from kotaemon.artifact_paths import validate_portable_component
from kotaemon.artifact_types import ArtifactNamespaceError


class ArtifactCleanupError(RuntimeError):
    """An artifact namespace cannot be safely removed."""


class FileArtifactCleaner:
    """Remove only the generated namespaces belonging to one file ID."""

    def __init__(
        self,
        *,
        chunks_root: str | Path,
        markdown_root: str | Path,
        download_root: str | Path,
    ) -> None:
        self._chunks_root = Path(chunks_root)
        self._markdown_root = Path(markdown_root)
        self._download_root = Path(download_root)

    @classmethod
    def from_settings(cls, settings: Any) -> FileArtifactCleaner:
        """Build the cleaner from the stable MARA artifact-root settings."""
        return cls(
            chunks_root=settings.KH_CHUNKS_OUTPUT_DIR,
            markdown_root=settings.KH_MARKDOWN_OUTPUT_DIR,
            download_root=settings.KH_ZIP_OUTPUT_DIR,
        )

    def clean(self, file_id: str) -> None:
        """Validate every exact namespace before removing any of them."""
        token = _file_id_token(file_id)
        targets = self._targets(token)
        present = [target for target in targets if _validate_tree(target)]
        for target in present:
            _remove_tree(target)

    def _targets(self, file_id: str) -> tuple[Path, ...]:
        return (
            self._chunks_root / file_id,
            self._markdown_root / file_id,
            self._download_root / "manifests" / "v1" / file_id,
            self._download_root / "downloads" / file_id,
        )


def _file_id_token(file_id: str) -> str:
    try:
        return validate_portable_component(str(file_id))
    except ArtifactNamespaceError as exc:
        raise ArtifactCleanupError("invalid file-id artifact namespace") from exc


def _validate_tree(target: Path) -> bool:
    if not _validate_prefix(target):
        return False
    mode = target.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ArtifactCleanupError(f"artifact namespace is a symlink: {target}")
    if not stat.S_ISDIR(mode):
        raise ArtifactCleanupError(f"artifact namespace is not a directory: {target}")
    for root, directories, files in os.walk(target, followlinks=False):
        for name in (*directories, *files):
            candidate = Path(root) / name
            if stat.S_ISLNK(candidate.lstat().st_mode):
                raise ArtifactCleanupError(
                    f"artifact tree contains a symlink: {candidate}"
                )
    return True


def _validate_prefix(target: Path) -> bool:
    missing = False
    current = Path(target.anchor) if target.is_absolute() else Path()
    for part in target.parts[1:] if target.is_absolute() else target.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            missing = True
            continue
        if missing:
            raise ArtifactCleanupError(
                f"artifact path changed during validation: {target}"
            )
        if stat.S_ISLNK(mode):
            raise ArtifactCleanupError(f"artifact path contains a symlink: {current}")
        if current != target and not stat.S_ISDIR(mode):
            raise ArtifactCleanupError(f"artifact parent is not a directory: {current}")
    return not missing


def _remove_tree(target: Path) -> None:
    shutil.rmtree(target)


__all__ = ["ArtifactCleanupError", "FileArtifactCleaner"]
