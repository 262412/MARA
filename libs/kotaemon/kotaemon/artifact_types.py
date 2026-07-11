from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from typing import IO, BinaryIO


class ArtifactNamespaceError(ValueError):
    """Raised when an artifact namespace or manifest is unsafe."""


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    size: int
    links: int
    modified_ns: int
    changed_ns: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> FileIdentity:
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ArtifactNamespaceError("Artifact must be a single-link regular file")
        return cls(
            device=metadata.st_dev,
            inode=metadata.st_ino,
            size=metadata.st_size,
            links=metadata.st_nlink,
            modified_ns=metadata.st_mtime_ns,
            changed_ns=metadata.st_ctime_ns,
        )

    def validate_fd(self, fd: int, *, message: str) -> None:
        metadata = os.fstat(fd)
        current = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_nlink,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        expected = (
            self.device,
            self.inode,
            self.size,
            self.links,
            self.modified_ns,
            self.changed_ns,
        )
        if not stat.S_ISREG(metadata.st_mode) or current != expected:
            raise ArtifactNamespaceError(message)


@dataclass(frozen=True)
class ManifestArtifact:
    """A validated artifact held open across archive construction."""

    fd: int
    archive_name: str
    size: int
    identity: FileIdentity
    digest: str

    def open(self) -> BinaryIO:
        return os.fdopen(os.dup(self.fd), "rb")

    def close(self) -> None:
        os.close(self.fd)

    def copy_to(self, target: IO[bytes]) -> None:
        self._validate_current()
        copied_digest = sha256()
        with self.open() as source:
            source.seek(0)
            remaining = self.size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ArtifactNamespaceError(
                        "Artifact changed while constructing the download"
                    )
                target.write(chunk)
                copied_digest.update(chunk)
                remaining -= len(chunk)
            if source.read(1):
                raise ArtifactNamespaceError(
                    "Artifact changed while constructing the download"
                )
        self._validate_current()
        if (
            copied_digest.hexdigest() != self.digest
            or digest_fd(self.fd, self.size) != self.digest
        ):
            raise ArtifactNamespaceError(
                "Artifact changed while constructing the download"
            )

    def _validate_current(self) -> None:
        self.identity.validate_fd(
            self.fd,
            message="Artifact changed while constructing the download",
        )


def digest_fd(fd: int, size: int) -> str:
    digest = sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(1024 * 1024, size - offset), offset)
        if not chunk:
            raise ArtifactNamespaceError("Artifact changed while reading")
        digest.update(chunk)
        offset += len(chunk)
    if os.pread(fd, 1, size):
        raise ArtifactNamespaceError("Artifact changed while reading")
    return digest.hexdigest()


__all__ = [
    "ArtifactNamespaceError",
    "FileIdentity",
    "ManifestArtifact",
    "digest_fd",
]
