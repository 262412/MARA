import os

import pytest

from kotaemon.artifact_types import FileIdentity, ManifestArtifact


def test_manifest_fdopen_failure_closes_only_its_duplicate(tmp_path, monkeypatch):
    path = tmp_path / "artifact"
    path.write_bytes(b"owned")
    source = os.open(path, os.O_RDONLY)
    artifact = ManifestArtifact(
        source, "owned.md", 5, FileIdentity.from_stat(os.fstat(source)), ""
    )
    duplicate = os.dup
    owned = []

    def dup(fd):
        result = duplicate(fd)
        owned.append(result)
        return result

    def fail(*args):
        raise OSError("fdopen failed")

    monkeypatch.setattr(os, "dup", dup)
    monkeypatch.setattr(os, "fdopen", fail)
    try:
        with pytest.raises(OSError, match="fdopen failed"):
            artifact.open()
        assert os.fstat(source)
        with pytest.raises(OSError):
            os.fstat(owned[0])
    finally:
        for fd in [source, *owned]:
            try:
                os.close(fd)
            except OSError:
                pass


def test_manifest_close_never_reuses_its_old_descriptor_number(tmp_path, monkeypatch):
    path = tmp_path / "artifact"
    path.write_bytes(b"owned")
    source = os.open(path, os.O_RDONLY)
    artifact = ManifestArtifact(
        source, "owned.md", 5, FileIdentity.from_stat(os.fstat(source)), ""
    )
    close = os.close
    closed = []

    def record(fd):
        closed.append(fd)
        close(fd)

    monkeypatch.setattr(os, "close", record)
    artifact.close()
    artifact.close()
    assert closed == [source]
