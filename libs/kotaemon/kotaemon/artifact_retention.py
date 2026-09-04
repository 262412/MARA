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
# Lifecycle lock plus file-id, request, marker, and payload for every valid record.
MAX_GLOBAL_SCAN_ENTRIES = 1 + (4 * READY_OUTPUT_HARD_LIMIT)
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
    entry_names: tuple[str, ...] | None = None


@dataclass
class _ScanBudget:
    remaining: int


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
        scan_budget = _ScanBudget(MAX_GLOBAL_SCAN_ENTRIES)
        records = _scan_and_prune(downloads_fd, scan_budget)
        records = _prune_ready_limits(downloads_fd, records, scan_budget)
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


def _scan_and_prune(
    downloads_fd: int,
    scan_budget: _ScanBudget,
) -> list[_WorkspaceRecord]:
    now = time.time()
    records: list[_WorkspaceRecord] = []
    file_ids = [
        name
        for name in _bounded_names(downloads_fd, scan_budget)
        if name != _LIFECYCLE_LOCK_NAME
    ]
    for file_id in file_ids:
        try:
            file_fd = open_child_directory(downloads_fd, file_id, create=False)
        except ArtifactNamespaceError as exc:
            if _namespace_disappeared(exc):
                continue
            raise
        try:
            for request_name in _bounded_names(file_fd, scan_budget):
                record = _inspect_workspace(
                    file_fd,
                    file_id,
                    request_name,
                    now,
                    scan_budget,
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
    scan_budget: _ScanBudget,
) -> _WorkspaceRecord | None:
    try:
        request_fd = open_child_directory(parent_fd, request_name, create=False)
    except ArtifactNamespaceError as exc:
        if _namespace_disappeared(exc):
            return None
        raise
    try:
        active = _inspect_active(request_fd, now)
        if active is not None:
            state, modified, active_fd = active
            if state == "stale":
                record = _remove_or_retain_workspace(
                    parent_fd,
                    file_id,
                    request_name,
                    request_fd,
                    modified,
                    scan_budget,
                    active_fd=active_fd,
                )
                request_fd = -1
                return record
            os.close(active_fd)
            return _WorkspaceRecord(file_id, request_name, "active", modified)
        ready = _regular_entry(request_fd, ".ready")
        if ready is not None:
            age = max(0.0, now - ready.st_mtime)
            entry_names = None
            has_payload = True
            if age <= READY_OUTPUT_TTL_SECONDS:
                has_payload, entry_names = _download_payload_entries(
                    request_fd,
                    scan_budget,
                )
            if age > READY_OUTPUT_TTL_SECONDS or not has_payload:
                record = _remove_or_retain_workspace(
                    parent_fd,
                    file_id,
                    request_name,
                    request_fd,
                    ready.st_mtime,
                    scan_budget,
                    known_names=entry_names,
                )
                request_fd = -1
                return record
            return _WorkspaceRecord(
                file_id,
                request_name,
                "ready",
                ready.st_mtime,
                entry_names,
            )
        modified = os.fstat(request_fd).st_mtime
        if max(0.0, now - modified) > ACTIVE_WORKSPACE_TTL_SECONDS:
            record = _remove_or_retain_workspace(
                parent_fd,
                file_id,
                request_name,
                request_fd,
                modified,
                scan_budget,
            )
            request_fd = -1
            return record
        return _WorkspaceRecord(file_id, request_name, "pending", modified)
    finally:
        if request_fd >= 0:
            os.close(request_fd)


def _remove_or_retain_workspace(
    parent_fd: int,
    file_id: str,
    request_name: str,
    request_fd: int,
    modified: float,
    scan_budget: _ScanBudget,
    *,
    active_fd: int | None = None,
    known_names: tuple[str, ...] | None = None,
) -> _WorkspaceRecord | None:
    removed = _remove_workspace(
        parent_fd,
        request_name,
        request_fd,
        scan_budget,
        active_fd=active_fd,
        known_names=known_names,
    )
    if removed:
        return None
    return _WorkspaceRecord(file_id, request_name, "retained", modified)


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
    scan_budget: _ScanBudget,
) -> list[_WorkspaceRecord]:
    now = time.time()
    remaining = list(records)
    by_file: dict[str, list[_WorkspaceRecord]] = {}
    for record in remaining:
        if record.kind == "ready":
            by_file.setdefault(record.file_id, []).append(record)
    for ready in by_file.values():
        ready.sort(key=lambda item: (item.modified, item.request_name))
        for candidate in list(ready):
            if len(ready) <= READY_OUTPUT_LIMIT:
                break
            if now - candidate.modified < READY_FETCH_WINDOW_SECONDS:
                break
            if _delete_record(downloads_fd, candidate, scan_budget):
                ready.remove(candidate)
                remaining.remove(candidate)
    return _prune_global_capacity(downloads_fd, remaining, now, scan_budget)


def _prune_global_capacity(
    downloads_fd: int,
    records: list[_WorkspaceRecord],
    now: float,
    scan_budget: _ScanBudget,
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
        if _delete_record(downloads_fd, candidate, scan_budget):
            remaining.remove(candidate)
    return remaining


def _delete_record(
    downloads_fd: int,
    record: _WorkspaceRecord,
    scan_budget: _ScanBudget,
) -> bool:
    try:
        parent_fd = open_child_directory(downloads_fd, record.file_id, create=False)
    except ArtifactNamespaceError as exc:
        return isinstance(exc.__cause__, FileNotFoundError)
    try:
        try:
            request_fd = open_child_directory(
                parent_fd,
                record.request_name,
                create=False,
            )
        except ArtifactNamespaceError as exc:
            return isinstance(exc.__cause__, FileNotFoundError)
        removed = _remove_workspace(
            parent_fd,
            record.request_name,
            request_fd,
            scan_budget,
            known_names=record.entry_names,
        )
    finally:
        os.close(parent_fd)
    if removed:
        _remove_empty_file_namespace(downloads_fd, record.file_id)
    return removed


def _remove_workspace(
    parent_fd: int,
    request_name: str,
    request_fd: int,
    scan_budget: _ScanBudget,
    active_fd: int | None = None,
    known_names: tuple[str, ...] | None = None,
) -> bool:
    try:
        if active_fd is None and _entry_exists(request_fd, ".active"):
            return False
        names = (
            known_names
            if known_names is not None
            else tuple(_bounded_names(request_fd, scan_budget))
        )
        for name in names:
            metadata = os.stat(name, dir_fd=request_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                return False
        for name in names:
            unlink_at(request_fd, name)
    finally:
        if active_fd is not None:
            os.close(active_fd)
        os.close(request_fd)
    try:
        os.rmdir(request_name, dir_fd=parent_fd)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _bounded_names(directory_fd: int, scan_budget: _ScanBudget) -> list[str]:
    names: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            if scan_budget.remaining <= 0:
                raise ArtifactNamespaceError("Download lifecycle scan limit exceeded")
            scan_budget.remaining -= 1
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


def _download_payload_entries(
    directory_fd: int,
    scan_budget: _ScanBudget,
) -> tuple[bool, tuple[str, ...]]:
    names = tuple(_bounded_names(directory_fd, scan_budget))
    has_payload = any(
        name.endswith((".zip", ".html"))
        and _regular_entry(directory_fd, name) is not None
        for name in names
    )
    return has_payload, names


def _namespace_disappeared(exc: ArtifactNamespaceError) -> bool:
    return isinstance(exc.__cause__, FileNotFoundError)


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
