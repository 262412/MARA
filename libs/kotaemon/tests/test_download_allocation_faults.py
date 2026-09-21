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
