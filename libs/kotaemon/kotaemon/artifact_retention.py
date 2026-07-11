from __future__ import annotations

import importlib
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifact_identifiers import namespace_token
from .artifact_secure_fs import (
    create_exclusive_file_at,
    open_child_directory,
    open_directory_fd,
    unlink_at,
)
from .artifact_types import ArtifactNamespaceError

try:
    fcntl: Any = importlib.import_module("fcntl")
except ImportError:  # pragma: no cover - exercised on non-POSIX platforms
    fcntl = None

READY_OUTPUT_LIMIT = 32
READY_OUTPUT_HARD_LIMIT = 128
READY_OUTPUT_TTL_SECONDS = 24 * 60 * 60
READY_FETCH_WINDOW_SECONDS = 60
ACTIVE_WORKSPACE_TTL_SECONDS = 10 * 60
MAX_GLOBAL_SCAN_ENTRIES = 512
_LIFECYCLE_LOCK_NAME = ".lifecycle.lock"


@dataclass(frozen=True)
class WorkspaceAllocation:
    directory: Path
    request_name: str
    parent_fd: int
    directory_fd: int
    active_fd: int


@dataclass(frozen=True)
class _WorkspaceRecord:
    file_id: str
    request_name: str
    kind: str
    modified: float


def allocate_workspace(
    output_root: str | Path,
    file_id: object,
) -> WorkspaceAllocation:
    lock_api = _require_lifecycle_lock()
    token = namespace_token(file_id)
    downloads_path, downloads_fd = open_directory_fd(
        output_root,
        ("downloads",),
        create=True,
    )
    lock_fd = _acquire_lifecycle_lock(downloads_fd)
    try:
        records = _scan_and_prune(downloads_fd)
        records = _prune_ready_limits(downloads_fd, records)
        if len(records) >= READY_OUTPUT_HARD_LIMIT:
            raise ArtifactNamespaceError(
                "Download capacity is full; retry after active fetches complete"
            )
        return _allocate_locked(downloads_path, downloads_fd, token)
    finally:
        lock_api.flock(lock_fd, lock_api.LOCK_UN)
        os.close(lock_fd)
        os.close(downloads_fd)


def _acquire_lifecycle_lock(downloads_fd: int) -> int:
    lock_api = _require_lifecycle_lock()
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        lock_fd = os.open(_LIFECYCLE_LOCK_NAME, flags, 0o600, dir_fd=downloads_fd)
        metadata = os.fstat(lock_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ArtifactNamespaceError("Download lifecycle lock is unsafe")
        lock_api.flock(lock_fd, lock_api.LOCK_EX)
        return lock_fd
    except BaseException:
        if "lock_fd" in locals():
            os.close(lock_fd)
        raise


def _allocate_locked(
    downloads_path: Path,
    downloads_fd: int,
    file_id: str,
) -> WorkspaceAllocation:
    try:
        os.mkdir(file_id, mode=0o700, dir_fd=downloads_fd)
    except FileExistsError:
        pass
    parent_fd = open_child_directory(downloads_fd, file_id, create=False)
    request_name = ""
    directory_fd = -1
    active_fd = -1
    try:
        request_name, directory_fd = _create_request_directory(parent_fd)
        active_fd = _create_active_lease(directory_fd)
        return WorkspaceAllocation(
            directory=downloads_path / file_id / request_name,
            request_name=request_name,
            parent_fd=parent_fd,
            directory_fd=directory_fd,
            active_fd=active_fd,
        )
    except BaseException:
        if active_fd >= 0:
            os.close(active_fd)
        if directory_fd >= 0:
            os.close(directory_fd)
        if request_name:
            try:
                os.rmdir(request_name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)
        raise


def _create_request_directory(parent_fd: int) -> tuple[str, int]:
    for _attempt in range(10):
        request_name = uuid4().hex
        try:
            os.mkdir(request_name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        return request_name, open_child_directory(
            parent_fd,
            request_name,
            create=False,
        )
    raise ArtifactNamespaceError("Unable to allocate a download workspace")


def _create_active_lease(directory_fd: int) -> int:
    lock_api = _require_lifecycle_lock()
    active_fd = create_exclusive_file_at(directory_fd, ".active")
    try:
        lock_api.flock(active_fd, lock_api.LOCK_EX | lock_api.LOCK_NB)
        os.write(active_fd, str(time.time_ns()).encode("ascii"))
        os.fsync(active_fd)
        os.fsync(directory_fd)
        return active_fd
    except BaseException:
        os.close(active_fd)
        unlink_at(directory_fd, ".active")
        raise


def _scan_and_prune(downloads_fd: int) -> list[_WorkspaceRecord]:
    now = time.time()
    records: list[_WorkspaceRecord] = []
    file_ids = [
        name for name in _bounded_names(downloads_fd) if name != _LIFECYCLE_LOCK_NAME
    ]
    for file_id in file_ids:
        try:
            file_fd = open_child_directory(downloads_fd, file_id, create=False)
        except ArtifactNamespaceError:
            continue
        try:
            for request_name in _bounded_names(file_fd):
                record = _inspect_workspace(
                    file_fd,
                    file_id,
                    request_name,
                    now,
                )
                if record is not None:
                    records.append(record)
        finally:
            os.close(file_fd)
        _remove_empty_file_namespace(downloads_fd, file_id)
    return records


def _inspect_workspace(
    parent_fd: int,
    file_id: str,
    request_name: str,
    now: float,
) -> _WorkspaceRecord | None:
    try:
        request_fd = open_child_directory(parent_fd, request_name, create=False)
    except ArtifactNamespaceError:
        return None
    try:
        active = _inspect_active(request_fd, now)
        if active is not None:
            state, modified, active_fd = active
            if state == "stale":
                _remove_workspace(parent_fd, request_name, request_fd, active_fd)
                request_fd = -1
                return None
            os.close(active_fd)
            return _WorkspaceRecord(file_id, request_name, "active", modified)
        ready = _regular_entry(request_fd, ".ready")
        if ready is not None:
            age = max(0.0, now - ready.st_mtime)
            if age > READY_OUTPUT_TTL_SECONDS or not _has_download_payload(request_fd):
                _remove_workspace(parent_fd, request_name, request_fd)
                request_fd = -1
                return None
            return _WorkspaceRecord(file_id, request_name, "ready", ready.st_mtime)
        modified = os.fstat(request_fd).st_mtime
        if max(0.0, now - modified) > ACTIVE_WORKSPACE_TTL_SECONDS:
            _remove_workspace(parent_fd, request_name, request_fd)
            request_fd = -1
            return None
        return _WorkspaceRecord(
            file_id,
            request_name,
            "pending",
            modified,
        )
    finally:
        if request_fd >= 0:
            os.close(request_fd)


def _inspect_active(
    request_fd: int,
    now: float,
) -> tuple[str, float, int] | None:
    lock_api = _require_lifecycle_lock()
    active_fd = _open_regular_entry(request_fd, ".active")
    if active_fd is None:
        return None
    metadata = os.fstat(active_fd)
    try:
        lock_api.flock(active_fd, lock_api.LOCK_EX | lock_api.LOCK_NB)
    except BlockingIOError:
        return "live", metadata.st_mtime, active_fd
    age = max(0.0, now - metadata.st_mtime)
    state = "stale" if age > ACTIVE_WORKSPACE_TTL_SECONDS else "pending"
    return state, metadata.st_mtime, active_fd


def _prune_ready_limits(
    downloads_fd: int,
    records: list[_WorkspaceRecord],
) -> list[_WorkspaceRecord]:
    now = time.time()
    remaining = list(records)
    by_file: dict[str, list[_WorkspaceRecord]] = {}
    for record in remaining:
        if record.kind == "ready":
            by_file.setdefault(record.file_id, []).append(record)
    for ready in by_file.values():
        ready.sort(key=lambda item: (item.modified, item.request_name))
        while len(ready) > READY_OUTPUT_LIMIT:
            candidate = ready[0]
            if now - candidate.modified < READY_FETCH_WINDOW_SECONDS:
                break
            _delete_record(downloads_fd, candidate)
            ready.pop(0)
            remaining.remove(candidate)
    return _prune_global_capacity(downloads_fd, remaining, now)


def _prune_global_capacity(
    downloads_fd: int,
    records: list[_WorkspaceRecord],
    now: float,
) -> list[_WorkspaceRecord]:
    remaining = list(records)
    eligible = sorted(
        (
            item
            for item in remaining
            if item.kind == "ready"
            and now - item.modified >= READY_FETCH_WINDOW_SECONDS
        ),
        key=lambda item: (item.modified, item.file_id, item.request_name),
    )
    while len(remaining) >= READY_OUTPUT_HARD_LIMIT and eligible:
        candidate = eligible.pop(0)
        _delete_record(downloads_fd, candidate)
        remaining.remove(candidate)
    return remaining


def _delete_record(downloads_fd: int, record: _WorkspaceRecord) -> None:
    try:
        parent_fd = open_child_directory(downloads_fd, record.file_id, create=False)
    except ArtifactNamespaceError:
        return
    try:
        try:
            request_fd = open_child_directory(
                parent_fd,
                record.request_name,
                create=False,
            )
        except ArtifactNamespaceError:
            return
        _remove_workspace(parent_fd, record.request_name, request_fd)
    finally:
        os.close(parent_fd)
    _remove_empty_file_namespace(downloads_fd, record.file_id)


def _remove_workspace(
    parent_fd: int,
    request_name: str,
    request_fd: int,
    active_fd: int | None = None,
) -> None:
    try:
        if active_fd is None and _entry_exists(request_fd, ".active"):
            return
        for name in _bounded_names(request_fd):
            metadata = os.stat(name, dir_fd=request_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                return
        for name in _bounded_names(request_fd):
            unlink_at(request_fd, name)
    finally:
        if active_fd is not None:
            os.close(active_fd)
        os.close(request_fd)
    try:
        os.rmdir(request_name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def _bounded_names(directory_fd: int) -> list[str]:
    names: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            if len(names) >= MAX_GLOBAL_SCAN_ENTRIES:
                raise ArtifactNamespaceError("Download lifecycle scan limit exceeded")
            names.append(entry.name)
    return names


def _open_regular_entry(directory_fd: int, name: str) -> int | None:
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        os.close(fd)
        raise ArtifactNamespaceError("Download lifecycle marker is unsafe")
    return fd


def _regular_entry(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return metadata if stat.S_ISREG(metadata.st_mode) else None


def _entry_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _has_download_payload(directory_fd: int) -> bool:
    return any(
        name.endswith((".zip", ".html"))
        and _regular_entry(directory_fd, name) is not None
        for name in _bounded_names(directory_fd)
    )


def _remove_empty_file_namespace(downloads_fd: int, file_id: str) -> None:
    try:
        os.rmdir(file_id, dir_fd=downloads_fd)
    except OSError:
        pass


def _require_lifecycle_lock():
    if fcntl is None:
        raise ArtifactNamespaceError(
            "Download lifecycle locking is unsupported on this platform"
        )
    return fcntl


__all__ = [
    "ACTIVE_WORKSPACE_TTL_SECONDS",
    "MAX_GLOBAL_SCAN_ENTRIES",
    "READY_FETCH_WINDOW_SECONDS",
    "READY_OUTPUT_HARD_LIMIT",
    "READY_OUTPUT_LIMIT",
    "READY_OUTPUT_TTL_SECONDS",
    "WorkspaceAllocation",
    "allocate_workspace",
]
