from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _cleanup_api():
    return importlib.import_module("ktem.index.file.artifact_cleanup")


def _cleaner(tmp_path):
    chunks = tmp_path / "chunks"
    markdown = tmp_path / "markdown"
    downloads = tmp_path / "zip"
    for root in (chunks, markdown, downloads):
        root.mkdir()
    cleaner = _cleanup_api().FileArtifactCleaner(
        chunks_root=chunks,
        markdown_root=markdown,
        download_root=downloads,
    )
    return cleaner, chunks, markdown, downloads


def _write_namespaces(chunks: Path, markdown: Path, downloads: Path) -> None:
    for root in (chunks, markdown):
        for file_id, marker in (
            ("file-owner", b"OWNER"),
            ("file-other", b"OTHER"),
            ("shared-hash", b"HASH"),
        ):
            path = root / file_id / "generation"
            path.mkdir(parents=True)
            (path / "artifact.bin").write_bytes(marker)
    for prefix in (downloads / "manifests" / "v1", downloads / "downloads"):
        for file_id in ("file-owner", "file-other", "shared-hash"):
            path = prefix / file_id
            path.mkdir(parents=True)
            (path / "artifact.bin").write_bytes(file_id.encode())


def test_artifact_cleaner_removes_only_exact_file_id_namespace(tmp_path):
    cleaner, chunks, markdown, downloads = _cleaner(tmp_path)
    _write_namespaces(chunks, markdown, downloads)

    cleaner.clean("file-owner")

    assert not (chunks / "file-owner").exists()
    assert not (markdown / "file-owner").exists()
    assert not (downloads / "manifests" / "v1" / "file-owner").exists()
    assert not (downloads / "downloads" / "file-owner").exists()
    for file_id in ("file-other", "shared-hash"):
        assert (chunks / file_id).is_dir()
        assert (markdown / file_id).is_dir()
        assert (downloads / "manifests" / "v1" / file_id).is_dir()
        assert (downloads / "downloads" / file_id).is_dir()


def test_artifact_cleaner_missing_namespace_is_idempotent(tmp_path):
    cleaner, _chunks, _markdown, _downloads = _cleaner(tmp_path)

    cleaner.clean("missing-file")
    cleaner.clean("missing-file")


@pytest.mark.parametrize("location", ["namespace", "generation"])
def test_artifact_cleaner_rejects_symlinks_without_touching_victim(
    tmp_path,
    location,
):
    cleaner, chunks, _markdown, _downloads = _cleaner(tmp_path)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.bin").write_bytes(b"keep")
    namespace = chunks / "file-owner"
    if location == "namespace":
        namespace.symlink_to(victim, target_is_directory=True)
    else:
        namespace.mkdir()
        (namespace / "generation").symlink_to(victim, target_is_directory=True)

    with pytest.raises(_cleanup_api().ArtifactCleanupError, match="symlink"):
        cleaner.clean("file-owner")

    assert (victim / "keep.bin").read_bytes() == b"keep"


def test_artifact_cleaner_rejects_non_directory_namespace(tmp_path):
    cleaner, chunks, _markdown, _downloads = _cleaner(tmp_path)
    (chunks / "file-owner").write_bytes(b"unexpected")

    with pytest.raises(_cleanup_api().ArtifactCleanupError, match="directory"):
        cleaner.clean("file-owner")

    assert (chunks / "file-owner").read_bytes() == b"unexpected"
