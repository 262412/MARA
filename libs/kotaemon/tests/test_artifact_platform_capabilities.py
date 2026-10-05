"""Keep native positioned reads and unsupported-platform refusals explicit."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from kotaemon import artifact_manifest
from kotaemon.artifact_secure_fs import open_regular_file
from kotaemon.artifact_types import ArtifactNamespaceError, FileIdentity, digest_fd


def test_missing_pread_preserves_open_descriptor_and_offset(monkeypatch, tmp_path):
    source = tmp_path / "artifact.bin"
    source.write_bytes(b"owned artifact")
    monkeypatch.delattr(os, "pread", raising=False)
    with source.open("rb") as stream:
        stream.seek(3)
        with pytest.raises(AttributeError, match="pread"):
            digest_fd(stream.fileno(), source.stat().st_size)
        assert os.lseek(stream.fileno(), 0, os.SEEK_CUR) == 3
        assert os.fstat(stream.fileno()).st_size == source.stat().st_size


def test_secure_open_refuses_missing_dir_fd_before_creating_paths(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(os, "supports_dir_fd", set())
    root = tmp_path / "not-created"
    with pytest.raises(ArtifactNamespaceError, match="unsupported on this platform"):
        open_regular_file(root, ("artifact.bin",))
    assert not root.exists()


def test_manifest_platform_refusal_precedes_missing_pread(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "supports_dir_fd", set())
    monkeypatch.delattr(os, "pread", raising=False)
    with pytest.raises(ArtifactNamespaceError, match="unsupported on this platform"):
        artifact_manifest._read_manifest(tmp_path, "owned-file")


@pytest.mark.skipif(not hasattr(os, "pread"), reason="requires native positioned I/O")
def test_concurrent_digests_preserve_shared_descriptor_offset(tmp_path):
    payload = b"owned artifact\n" * 90_000
    source = tmp_path / "artifact.bin"
    source.write_bytes(payload)
    with source.open("rb") as stream:
        stream.seek(11)
        duplicate = os.dup(stream.fileno())
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda fd: digest_fd(fd, len(payload)),
                        [stream.fileno(), duplicate],
                    )
                )
            assert results == [hashlib.sha256(payload).hexdigest()] * 2
            assert os.lseek(stream.fileno(), 0, os.SEEK_CUR) == 11
            assert os.lseek(duplicate, 0, os.SEEK_CUR) == 11
        finally:
            os.close(duplicate)


@pytest.mark.skipif(not hasattr(os, "pread"), reason="requires native positioned I/O")
@pytest.mark.parametrize("size_delta", [-1, 1])
def test_digest_rejects_wrong_size_without_moving_offset(tmp_path, size_delta):
    source = tmp_path / "artifact.bin"
    source.write_bytes(b"owned artifact")
    with source.open("rb") as stream:
        stream.seek(3)
        with pytest.raises(ArtifactNamespaceError, match="changed while reading"):
            digest_fd(stream.fileno(), source.stat().st_size + size_delta)
        assert os.lseek(stream.fileno(), 0, os.SEEK_CUR) == 3


@pytest.mark.skipif(os.name != "posix", reason="requires secure native dir_fd I/O")
@pytest.mark.parametrize("rewrite", [False, True])
def test_manifest_positioned_recheck_detects_rewrite_after_identity_check(
    monkeypatch, tmp_path, rewrite
):
    record = {"version": 1, "file_id": "old-id", "entries": []}
    manifest = tmp_path / "manifests" / "v1" / "old-id" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = json.dumps(record).encode()
    manifest.write_bytes(payload)
    original = FileIdentity.validate_fd

    def validate_then_rewrite(identity, fd, *, message):
        original(identity, fd, message=message)
        if rewrite:
            manifest.write_bytes(payload.replace(b"old-id", b"new-id"))

    monkeypatch.setattr(FileIdentity, "validate_fd", validate_then_rewrite)
    if rewrite:
        with pytest.raises(ArtifactNamespaceError, match="changed while reading"):
            artifact_manifest._read_manifest(tmp_path, "old-id")
    else:
        assert artifact_manifest._read_manifest(tmp_path, "old-id") == record
