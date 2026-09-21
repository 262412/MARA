from __future__ import annotations

import json
import logging
import os
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .artifact_retention import (
    ACTIVE_WORKSPACE_TTL_SECONDS,
    MAX_GLOBAL_SCAN_ENTRIES,
    READY_FETCH_WINDOW_SECONDS,
    READY_OUTPUT_HARD_LIMIT,
    READY_OUTPUT_LIMIT,
    READY_OUTPUT_TTL_SECONDS,
    _require_lifecycle_lock,
    allocate_workspace,
)
from .artifact_secure_fs import create_exclusive_file_at, replace_at, unlink_at
from .artifact_types import ArtifactNamespaceError

logger = logging.getLogger(__name__)


@dataclass
class DownloadWorkspace:
    directory: Path
    output_path: Path
    _request_name: str
    _output_name: str
    _parent_fd: int
    _directory_fd: int
    _active_fd: int
    _temporary_name: str | None = None
    _closed: bool = False
    _ready_fd: int = -1

    @classmethod
    def create(
        cls,
        output_root: str | Path,
        file_id: object,
        suffix: str,
    ) -> DownloadWorkspace:
        if suffix not in {".zip", ".html"}:
            raise ArtifactNamespaceError("Invalid download suffix")
        allocation = allocate_workspace(output_root, file_id)
        output_name = f"download-{allocation.request_name}{suffix}"
        return cls(
            directory=allocation.directory,
            output_path=allocation.directory / output_name,
            _request_name=allocation.request_name,
            _output_name=output_name,
            _parent_fd=allocation.parent_fd,
            _directory_fd=allocation.directory_fd,
            _active_fd=allocation.active_fd,
        )

    def open_temporary(self):
        if self._temporary_name is not None:
            raise ArtifactNamespaceError("Download temporary file already exists")
        self._temporary_name = f".download-{uuid4().hex}.tmp"
        fd = create_exclusive_file_at(self._directory_fd, self._temporary_name)
        try:
            return os.fdopen(fd, "w+b")
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                logger.exception("Failed to close download temporary descriptor")
            raise

    def publish(self, *, context: dict | None = None) -> Path:
        if self._temporary_name is None:
            raise ArtifactNamespaceError("Download temporary file is unavailable")
        replace_at(self._directory_fd, self._temporary_name, self._output_name)
        self._temporary_name = None
        self._write_marker(".ready", context=context)
        unlink_at(self._directory_fd, ".active")
        self._release_active_lease()
        os.fsync(self._directory_fd)
        self.close()
        return self.output_path

    def cleanup(self) -> None:
        if self._closed:
            return
        try:
            for name in os.listdir(self._directory_fd):
                try:
                    metadata = os.stat(
                        name,
                        dir_fd=self._directory_fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(metadata.st_mode):
                    continue
                unlink_at(self._directory_fd, name)
        finally:
            self._finish(remove=True)

    def close(self) -> None:
        self._finish(remove=False)

    def _finish(self, *, remove: bool) -> None:
        if self._closed:
            return
        primary = sys.exc_info()[1]
        errors = []
        self._closed = True
        for attribute in ("_ready_fd", "_active_fd", "_directory_fd", "_parent_fd"):
            if remove and attribute == "_parent_fd":
                try:
                    os.rmdir(self._request_name, dir_fd=self._parent_fd)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    errors.append(exc)
                    logger.exception(
                        "Failed to remove owned download directory %s", self.directory
                    )
            fd = getattr(self, attribute)
            # A failing close can already have released the OS handle. Never
            # retry its numeric descriptor, which may now belong to another user.
            setattr(self, attribute, -1)
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as exc:
                    errors.append(exc)
                    logger.exception(
                        "Failed to release download descriptor %s", attribute
                    )
        if errors and primary is None:
            raise errors[0]

    def _write_marker(self, name: str, *, context: dict | None = None) -> None:
        fd = create_exclusive_file_at(self._directory_fd, name)
        try:
            marker = os.fdopen(fd, "wb")
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                logger.exception("Failed to close download marker descriptor")
            raise
        with marker:
            lock_api = _require_lifecycle_lock()
            lock_api.flock(marker.fileno(), lock_api.LOCK_EX | lock_api.LOCK_NB)
            content = str(time.time_ns()) if context is None else json.dumps(context)
            marker.write(content.encode("utf-8"))
            marker.flush()
            os.fsync(marker.fileno())
            self._ready_fd = os.dup(marker.fileno())
        os.fsync(self._directory_fd)

    def _release_active_lease(self) -> None:
        if self._active_fd >= 0:
            fd = self._active_fd
            self._active_fd = -1
            os.close(fd)


__all__ = [
    "ACTIVE_WORKSPACE_TTL_SECONDS",
    "DownloadWorkspace",
    "MAX_GLOBAL_SCAN_ENTRIES",
    "READY_FETCH_WINDOW_SECONDS",
    "READY_OUTPUT_HARD_LIMIT",
    "READY_OUTPUT_LIMIT",
    "READY_OUTPUT_TTL_SECONDS",
]
