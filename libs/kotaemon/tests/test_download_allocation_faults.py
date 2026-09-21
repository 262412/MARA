"""Partial allocation owns its handles even when cleanup itself reports failure."""

import os
from types import SimpleNamespace

import pytest

from kotaemon import artifact_retention as retention


def test_request_open_failure_removes_only_its_new_empty_directory(monkeypatch):
    created, removed = [], []
    monkeypatch.setattr(retention.os, "mkdir", lambda name, **kw: created.append(name))
    monkeypatch.setattr(retention.os, "rmdir", lambda name, **kw: removed.append(name))

    def fail(*args, **kwargs):
        raise OSError("open request failed")

    monkeypatch.setattr(retention, "open_child_directory", fail)
    with pytest.raises(OSError, match="open request failed"):
        retention._create_request_directory(73)
    assert removed == created
    assert len(created) == 1


def test_active_creation_preserves_primary_and_attempts_unlink(tmp_path, monkeypatch):
    fd = os.open(tmp_path / "active", os.O_CREAT | os.O_RDWR, 0o600)
    close = os.close
    removed = []

    def fail_lock(*args):
        raise RuntimeError("primary lock failure")

    def fail_close(number):
        close(number)
        raise OSError("secondary close failure")

    monkeypatch.setattr(retention, "create_exclusive_file_at", lambda *_: fd)
    monkeypatch.setattr(
        retention,
        "_require_lifecycle_lock",
        lambda: SimpleNamespace(flock=fail_lock, LOCK_EX=1, LOCK_NB=2),
    )
    monkeypatch.setattr(retention.os, "close", fail_close)
    monkeypatch.setattr(retention, "unlink_at", lambda *args: removed.append(args))
    with pytest.raises(RuntimeError, match="primary lock failure"):
        retention._create_active_lease(73)
    assert removed == [(73, ".active")]


def test_allocation_preserves_scan_failure_after_close_error(tmp_path, monkeypatch):
    fd = os.open(tmp_path / "root", os.O_CREAT | os.O_RDWR, 0o600)
    lock_fd = os.open(tmp_path / "lock", os.O_CREAT | os.O_RDWR, 0o600)
    close = os.close
    closed = []
    monkeypatch.setattr(
        retention,
        "_require_lifecycle_lock",
        lambda: SimpleNamespace(flock=lambda *_: None, LOCK_UN=8),
    )
    monkeypatch.setattr(retention, "open_directory_fd", lambda *a, **kw: (tmp_path, fd))
    monkeypatch.setattr(retention, "_acquire_lifecycle_lock", lambda *_: lock_fd)

    def fail_scan(*args):
        raise RuntimeError("primary scan failure")

    def fail_close(number):
        closed.append(number)
        close(number)
        if number == lock_fd:
            raise OSError("secondary close failure")

    monkeypatch.setattr(retention, "_scan_and_prune", fail_scan)
    monkeypatch.setattr(retention.os, "close", fail_close)
    with pytest.raises(RuntimeError, match="primary scan failure"):
        retention.allocate_workspace(tmp_path, "owned")
    assert closed == [lock_fd, fd]


@pytest.mark.parametrize("secondary", [None, "unlink", "close", "rmdir"])
def test_unlock_failure_discards_completed_allocation_and_preserves_primary(
    tmp_path, monkeypatch, secondary
):
    # Real handles exercise release; directory operations are portable fault seams.
    descriptors = {
        name: os.open(tmp_path / name, os.O_CREAT | os.O_RDWR, 0o600)
        for name in ("root", "lock", "parent", "request", "active")
    }
    close = os.close
    closed, removed = [], []
    unrelated = tmp_path / "unrelated"
    unrelated.write_bytes(b"preserve")
    allocation = retention.WorkspaceAllocation(
        tmp_path / "owned",
        "owned",
        descriptors["parent"],
        descriptors["request"],
        descriptors["active"],
    )

    def unlock(*args):
        raise OSError("primary unlock failure")

    def close_owned(fd):
        closed.append(fd)
        close(fd)
        if secondary == "close" and fd == descriptors["active"]:
            raise OSError("secondary close failure")

    def unlink(fd, name):
        removed.append((fd, name))
        if secondary == "unlink":
            raise OSError("secondary unlink failure")

    def rmdir(name, *, dir_fd):
        removed.append((dir_fd, name))
        if secondary == "rmdir":
            raise OSError("secondary rmdir failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            retention,
            "_require_lifecycle_lock",
            lambda: SimpleNamespace(flock=unlock, LOCK_UN=8),
        )
        patch.setattr(
            retention,
            "open_directory_fd",
            lambda *a, **kw: (tmp_path, descriptors["root"]),
        )
        patch.setattr(
            retention, "_acquire_lifecycle_lock", lambda *_: descriptors["lock"]
        )
        patch.setattr(retention, "_scan_and_prune", lambda *_: [])
        patch.setattr(retention, "_prune_ready_limits", lambda *args: args[1])
        patch.setattr(retention, "_allocate_locked", lambda *_: allocation)
        patch.setattr(retention, "unlink_at", unlink)
        patch.setattr(retention.os, "rmdir", rmdir)
        patch.setattr(retention.os, "close", close_owned)
        with pytest.raises(OSError, match="primary unlock failure"):
            retention.allocate_workspace(tmp_path, "file")
    assert closed == [
        descriptors[key] for key in ("lock", "root", "active", "request", "parent")
    ]
    assert removed == [
        (descriptors["request"], ".active"),
        (descriptors["parent"], "owned"),
    ]
    for fd in descriptors.values():
        with pytest.raises(OSError):
            os.fstat(fd)
    assert unrelated.read_bytes() == b"preserve"
