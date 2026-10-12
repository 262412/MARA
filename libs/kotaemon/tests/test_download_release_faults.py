"""Owned descriptor failures are observable on both native platforms."""

import os
from types import SimpleNamespace

import pytest

from kotaemon.artifact_downloads import DownloadWorkspace
from kotaemon.artifact_types import (
    ArtifactNamespaceError,
    FileIdentity,
    ManifestArtifact,
)


@pytest.mark.parametrize("failed_slot", ["active", "directory", "parent"])
def test_close_attempts_every_owned_descriptor_once(tmp_path, monkeypatch, failed_slot):
    descriptors = {
        name: os.open(tmp_path / name, os.O_CREAT | os.O_RDWR, 0o600)
        for name in ("active", "directory", "parent", "borrowed")
    }
    workspace = DownloadWorkspace(
        directory=tmp_path,
        output_path=tmp_path / "output.zip",
        _request_name="owned",
        _output_name="output.zip",
        _parent_fd=descriptors["parent"],
        _directory_fd=descriptors["directory"],
        _active_fd=descriptors["active"],
    )
    close = os.close
    closed = []

    def close_then_fail(fd):
        closed.append(fd)
        close(fd)
        if fd == descriptors[failed_slot]:
            raise OSError(f"{failed_slot} close failed")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(os, "close", close_then_fail)
            with pytest.raises(OSError, match=f"{failed_slot} close failed"):
                workspace.close()
            assert set(closed) == {
                descriptors[key] for key in ("active", "directory", "parent")
            }
            assert len(closed) == 3
            workspace.close()
            assert len(closed) == 3
        assert workspace._closed
        assert os.fstat(descriptors["borrowed"])
    finally:
        for fd in descriptors.values():
            if fd not in closed:
                close(fd)


def test_open_temporary_fdopen_failure_releases_new_descriptor(tmp_path, monkeypatch):
    import kotaemon.artifact_downloads as downloads

    fd = os.open(tmp_path / "exclusive.tmp", os.O_CREAT | os.O_RDWR, 0o600)
    workspace = DownloadWorkspace(
        tmp_path, tmp_path / "output.zip", "owned", "output.zip", -1, -1, -1
    )
    monkeypatch.setattr(downloads, "create_exclusive_file_at", lambda *_: fd)

    def fail(*args):
        raise OSError("fdopen failed")

    monkeypatch.setattr(downloads.os, "fdopen", fail)
    try:
        with pytest.raises(OSError, match="fdopen failed"):
            workspace.open_temporary()
        with pytest.raises(OSError):
            os.fstat(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def test_allocation_lock_failure_releases_root_descriptor(tmp_path, monkeypatch):
    from kotaemon import artifact_retention as retention

    fd = os.open(tmp_path / "root-handle", os.O_CREAT | os.O_RDWR, 0o600)
    monkeypatch.setattr(retention, "_require_lifecycle_lock", lambda: SimpleNamespace())
    monkeypatch.setattr(retention, "open_directory_fd", lambda *a, **kw: (tmp_path, fd))

    def fail(*args):
        raise OSError("lock failed")

    monkeypatch.setattr(retention, "_acquire_lifecycle_lock", fail)
    try:
        with pytest.raises(OSError, match="lock failed"):
            retention.allocate_workspace(tmp_path, "owned")
        with pytest.raises(OSError):
            os.fstat(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def test_ready_marker_fdopen_failure_releases_new_descriptor(tmp_path, monkeypatch):
    from kotaemon import artifact_downloads as downloads

    fd = os.open(tmp_path / ".ready", os.O_CREAT | os.O_RDWR, 0o600)
    workspace = DownloadWorkspace(
        tmp_path, tmp_path / "output.zip", "owned", "output.zip", -1, -1, -1
    )
    monkeypatch.setattr(downloads, "create_exclusive_file_at", lambda *_: fd)

    def fail(*args):
        raise OSError("marker fdopen failed")

    monkeypatch.setattr(downloads.os, "fdopen", fail)
    try:
        with pytest.raises(OSError, match="marker fdopen failed"):
            workspace._write_marker(".ready")
        with pytest.raises(OSError):
            os.fstat(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def test_manifest_key_failure_closes_the_just_opened_artifact(tmp_path, monkeypatch):
    from kotaemon import artifact_manifest as manifest

    fd = os.open(tmp_path / "owned.md", os.O_CREAT | os.O_RDWR, 0o600)
    artifact = ManifestArtifact(
        fd, "chunks/owned.md", 0, FileIdentity.from_stat(os.fstat(fd)), ""
    )
    monkeypatch.setattr(
        manifest,
        "_read_manifest",
        lambda *args: {
            "version": 1,
            "file_id": "owned",
            "entries": [{"kind": "chunks", "relative_path": "owned/gen/a.md"}],
        },
    )

    def fail_key(*args):
        raise ArtifactNamespaceError("key normalization failed")

    monkeypatch.setattr(manifest, "portable_member_key", fail_key)
    try:
        with pytest.raises(ArtifactNamespaceError, match="key normalization"):
            manifest.load_manifest_artifacts(
                "owned", {}, tmp_path, resolve_entry=lambda *args: artifact
            )
        with pytest.raises(OSError):
            os.fstat(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
