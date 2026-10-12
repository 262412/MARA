"""Claim a ready download by safe FDs and hold its marker through HTTP transfer."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .artifact_identifiers import namespace_token
from .artifact_retention import (
    READY_OUTPUT_TTL_SECONDS,
    _acquire_lifecycle_lock,
    _close_owned,
    _entry_exists,
    _open_regular_entry,
    _require_lifecycle_lock,
)
from .artifact_secure_fs import open_child_directory, open_directory_fd
from .artifact_types import ArtifactNamespaceError, FileIdentity


@dataclass
class DownloadTransfer:
    fd: int
    marker_fd: int
    size: int
    filename: str

    def close(self):
        descriptors = self.fd, self.marker_fd
        self.fd = self.marker_fd = -1
        errors = _close_owned(*descriptors)
        if errors and sys.exc_info()[1] is None:
            raise errors[0]


def claim_download(
    root: str | Path, file_id: str, request_name: str, suffix: str, context: dict
) -> DownloadTransfer:
    if len(request_name) != 32 or any(
        c not in "0123456789abcdef" for c in request_name
    ):
        raise ArtifactNamespaceError("Invalid download request")
    if suffix not in {".zip", ".html"}:
        raise ArtifactNamespaceError("Invalid download suffix")
    lock_api = _require_lifecycle_lock()
    _root, root_fd = open_directory_fd(root, ("downloads",), create=False)
    lock_fd = parent_fd = directory_fd = marker_fd = payload_fd = -1
    try:
        lock_fd = _acquire_lifecycle_lock(root_fd)
        parent_fd = open_child_directory(
            root_fd, namespace_token(file_id), create=False
        )
        directory_fd = open_child_directory(parent_fd, request_name, create=False)
        if _entry_exists(directory_fd, ".active"):
            raise ArtifactNamespaceError("Download generation is still active")
        ready = _open_regular_entry(directory_fd, ".ready")
        if ready is None:
            raise ArtifactNamespaceError("Download is not ready")
        marker_fd = ready
        lock_api.flock(marker_fd, lock_api.LOCK_SH | lock_api.LOCK_NB)
        metadata = os.fstat(marker_fd)
        if (
            metadata.st_size > 8192
            or time.time() - metadata.st_mtime > READY_OUTPUT_TTL_SECONDS
        ):
            raise ArtifactNamespaceError("Download has expired")
        try:
            recorded = json.loads(os.read(marker_fd, 8193))
        except (ValueError, UnicodeError) as exc:
            raise ArtifactNamespaceError(
                "Download has no authorization receipt"
            ) from exc
        if recorded != context:
            raise ArtifactNamespaceError("Download authorization receipt changed")
        filename = f"download-{request_name}{suffix}"
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        payload_fd = os.open(filename, flags, dir_fd=directory_fd)
        identity = FileIdentity.from_stat(os.fstat(payload_fd))
        transfer = DownloadTransfer(payload_fd, marker_fd, identity.size, filename)
        payload_fd = marker_fd = -1
        return transfer
    finally:
        _close_owned(payload_fd, marker_fd, directory_fd, parent_fd, lock_fd, root_fd)
