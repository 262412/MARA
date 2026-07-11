from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .artifact_identifiers import namespace_token
from .artifact_secure_fs import (
    create_exclusive_file_at,
    open_child_directory,
    open_directory_fd,
    replace_at,
    unlink_at,
)
from .artifact_types import ArtifactNamespaceError

READY_OUTPUT_LIMIT = 32
READY_OUTPUT_HARD_LIMIT = 128
READY_OUTPUT_TTL_SECONDS = 24 * 60 * 60
READY_FETCH_WINDOW_SECONDS = 60


@dataclass
class DownloadWorkspace:
    directory: Path
    output_path: Path
    _request_name: str
    _output_name: str
    _parent_fd: int
    _directory_fd: int
    _temporary_name: str | None = None
    _closed: bool = False

    @classmethod
    def create(
        cls,
        output_root: str | Path,
        file_id: object,
        suffix: str,
    ) -> DownloadWorkspace:
        if suffix not in {".zip", ".html"}:
            raise ArtifactNamespaceError("Invalid download suffix")
        token = namespace_token(file_id)
        parent_path, parent_fd = open_directory_fd(
            output_root,
            ("downloads", token),
            create=True,
        )
        workspace = None
        try:
            _prune_ready_outputs(parent_fd)
            request_name, directory_fd = _create_request_directory(parent_fd)
            directory = parent_path / request_name
            output_name = f"download-{request_name}{suffix}"
            workspace = cls(
                directory=directory,
                output_path=directory / output_name,
                _request_name=request_name,
                _output_name=output_name,
                _parent_fd=parent_fd,
                _directory_fd=directory_fd,
            )
            workspace._write_marker(".active")
            return workspace
        except BaseException:
            if workspace is None:
                os.close(parent_fd)
            else:
                workspace.cleanup()
            raise

    def open_temporary(self):
        if self._temporary_name is not None:
            raise ArtifactNamespaceError("Download temporary file already exists")
        self._temporary_name = f".download-{uuid4().hex}.tmp"
        fd = create_exclusive_file_at(self._directory_fd, self._temporary_name)
        return os.fdopen(fd, "w+b")

    def publish(self) -> Path:
        if self._temporary_name is None:
            raise ArtifactNamespaceError("Download temporary file is unavailable")
        replace_at(self._directory_fd, self._temporary_name, self._output_name)
        self._temporary_name = None
        self._write_marker(".ready")
        unlink_at(self._directory_fd, ".active")
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
            os.close(self._directory_fd)
            try:
                os.rmdir(self._request_name, dir_fd=self._parent_fd)
            except FileNotFoundError:
                pass
            finally:
                os.close(self._parent_fd)
                self._closed = True

    def close(self) -> None:
        if self._closed:
            return
        os.close(self._directory_fd)
        os.close(self._parent_fd)
        self._closed = True

    def _write_marker(self, name: str) -> None:
        fd = create_exclusive_file_at(self._directory_fd, name)
        with os.fdopen(fd, "wb") as marker:
            marker.write(str(time.time_ns()).encode("ascii"))
            marker.flush()
            os.fsync(marker.fileno())
        os.fsync(self._directory_fd)


def _create_request_directory(parent_fd: int) -> tuple[str, int]:
    for _attempt in range(10):
        request_name = uuid4().hex
        try:
            os.mkdir(request_name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        try:
            return request_name, open_child_directory(
                parent_fd,
                request_name,
                create=False,
            )
        except BaseException:
            os.rmdir(request_name, dir_fd=parent_fd)
            raise
    raise ArtifactNamespaceError("Unable to allocate a download workspace")


def _prune_ready_outputs(parent_fd: int) -> None:
    now = time.time()
    ready: list[tuple[str, float]] = []
    for request_name in os.listdir(parent_fd):
        try:
            request_fd = open_child_directory(
                parent_fd,
                request_name,
                create=False,
            )
        except ArtifactNamespaceError:
            continue
        try:
            if _entry_exists(request_fd, ".active"):
                continue
            marker = _regular_entry(request_fd, ".ready")
            if marker is None:
                continue
            if not _has_download_payload(request_fd):
                _remove_request(parent_fd, request_name, request_fd)
                request_fd = -1
                continue
            age = max(0.0, now - marker.st_mtime)
            if age > READY_OUTPUT_TTL_SECONDS:
                _remove_request(parent_fd, request_name, request_fd)
                request_fd = -1
                continue
            ready.append((request_name, marker.st_mtime))
        finally:
            if request_fd >= 0:
                os.close(request_fd)

    ready.sort(key=lambda item: (item[1], item[0]))
    while len(ready) > READY_OUTPUT_LIMIT:
        request_name, modified = ready[0]
        if now - modified < READY_FETCH_WINDOW_SECONDS:
            break
        _remove_request_by_name(parent_fd, request_name)
        ready.pop(0)
    while len(ready) > READY_OUTPUT_HARD_LIMIT:
        request_name, _modified = ready.pop(0)
        _remove_request_by_name(parent_fd, request_name)


def _entry_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _regular_entry(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return metadata if stat.S_ISREG(metadata.st_mode) else None


def _has_download_payload(directory_fd: int) -> bool:
    return any(
        name.endswith((".zip", ".html"))
        and _regular_entry(directory_fd, name) is not None
        for name in os.listdir(directory_fd)
    )


def _remove_request_by_name(parent_fd: int, request_name: str) -> None:
    try:
        request_fd = open_child_directory(parent_fd, request_name, create=False)
    except ArtifactNamespaceError:
        return
    _remove_request(parent_fd, request_name, request_fd)


def _remove_request(parent_fd: int, request_name: str, request_fd: int) -> None:
    try:
        if _entry_exists(request_fd, ".active"):
            return
        for name in os.listdir(request_fd):
            metadata = os.stat(name, dir_fd=request_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                return
        for name in os.listdir(request_fd):
            unlink_at(request_fd, name)
    finally:
        os.close(request_fd)
    try:
        os.rmdir(request_name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


__all__ = ["DownloadWorkspace"]
