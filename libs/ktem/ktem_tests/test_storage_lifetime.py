from __future__ import annotations

import importlib
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


def _storage_api():
    return importlib.import_module("ktem.index.file.storage_lifetime")


@pytest.mark.parametrize("stored_path", ["../outside.bin", "/tmp/outside.bin"])
def test_storage_lifetime_rejects_paths_outside_root(tmp_path, stored_path):
    lifetime = _storage_api().StorageLifetime(tmp_path / "storage")

    with pytest.raises(ValueError, match="path"):
        with lifetime.hold(stored_path):
            pass


def test_storage_lease_quarantine_restore_and_purge(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    blob = storage / "shared.bin"
    blob.write_bytes(b"document")
    lifetime = _storage_api().StorageLifetime(storage)

    with lifetime.hold("shared.bin") as lease:
        first_move = lease.quarantine()
        assert first_move is not None
        assert not blob.exists()
        assert first_move.quarantine.read_bytes() == b"document"
        lease.restore(first_move)
        assert blob.read_bytes() == b"document"

        second_move = lease.quarantine()
        assert second_move is not None
        lease.purge(second_move)

    assert not blob.exists()
    assert not second_move.quarantine.exists()


def test_storage_lease_missing_blob_is_idempotent(tmp_path):
    lifetime = _storage_api().StorageLifetime(tmp_path / "storage")

    with lifetime.hold("missing.bin") as lease:
        assert lease.quarantine() is None


def test_quarantine_sync_failure_restores_original_blob(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    blob = storage / "shared.bin"
    blob.write_bytes(b"document")
    sync_calls = 0

    def fail_first_sync(_path) -> None:
        nonlocal sync_calls
        sync_calls += 1
        if sync_calls == 1:
            raise OSError("directory sync unavailable")

    lifetime = _storage_api().StorageLifetime(
        storage,
        directory_syncer=fail_first_sync,
    )

    with lifetime.hold("shared.bin") as lease:
        with pytest.raises(OSError, match="directory sync unavailable"):
            lease.quarantine()

    assert blob.read_bytes() == b"document"
    assert not list(storage.glob(".shared.bin.quarantine-*"))


def test_storage_lease_publish_is_atomic_and_idempotent(tmp_path):
    storage = tmp_path / "storage"
    source = tmp_path / "upload.bin"
    source.write_bytes(b"document")
    lifetime = _storage_api().StorageLifetime(storage)

    with lifetime.hold("shared.bin") as lease:
        lease.publish_from(source)
        lease.publish_from(source)

    assert (storage / "shared.bin").read_bytes() == b"document"
    assert not list(storage.glob("*.tmp"))


def test_directory_sync_is_a_noop_on_windows(monkeypatch, tmp_path):
    module = _storage_api()

    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: pytest.fail("Windows must not open a directory"),
    )

    module._fsync_directory(tmp_path)


def test_storage_lease_rejects_symlink_and_directory_blob(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    victim = storage / "victim.bin"
    victim.write_bytes(b"keep")
    symlink = storage / "linked.bin"
    symlink.symlink_to(victim)
    directory = storage / "directory.bin"
    directory.mkdir()
    lifetime = _storage_api().StorageLifetime(storage)

    for stored_path in ("linked.bin", "directory.bin"):
        with lifetime.hold(stored_path) as lease:
            with pytest.raises(ValueError, match="regular"):
                lease.quarantine()

    assert symlink.is_symlink()
    assert victim.read_bytes() == b"keep"
    assert directory.is_dir()


def test_two_lifetime_instances_serialize_the_same_path(tmp_path):
    storage = tmp_path / "storage"
    first = _storage_api().StorageLifetime(storage)
    second = _storage_api().StorageLifetime(storage)
    first_entered = threading.Event()
    second_attempted = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()

    def hold_first() -> None:
        with first.hold("shared.bin"):
            first_entered.set()
            assert release_first.wait(5)

    def hold_second() -> None:
        assert first_entered.wait(5)
        second_attempted.set()
        with second.hold("shared.bin"):
            second_entered.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(hold_first)
        second_future = executor.submit(hold_second)
        assert first_entered.wait(5)
        assert second_attempted.wait(5)
        assert not second_entered.wait(0.1)
        release_first.set()
        assert second_entered.wait(5)
        first_future.result(timeout=5)
        second_future.result(timeout=5)


def test_different_storage_paths_do_not_share_a_lock(tmp_path):
    storage = tmp_path / "storage"
    first = _storage_api().StorageLifetime(storage)
    second = _storage_api().StorageLifetime(storage)
    first_entered = threading.Event()
    second_entered = threading.Event()
    release_first = threading.Event()

    def hold_first() -> None:
        with first.hold("first.bin"):
            first_entered.set()
            assert release_first.wait(5)

    def hold_second() -> None:
        assert first_entered.wait(5)
        with second.hold("second.bin"):
            second_entered.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(hold_first)
        second_future = executor.submit(hold_second)
        assert second_entered.wait(5)
        release_first.set()
        first_future.result(timeout=5)
        second_future.result(timeout=5)
