from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from typing import IO, BinaryIO


class ArtifactNamespaceError(ValueError):
    """Raised when an artifact namespace or manifest is unsafe."""


@dataclass(frozen=True)
class ManifestArtifact:
    """A validated artifact held open across archive construction."""

    fd: int
    archive_name: str
    size: int
    device: int
    inode: int

    def open(self) -> BinaryIO:
        return os.fdopen(os.dup(self.fd), "rb")

    def close(self) -> None:
        os.close(self.fd)

    def copy_to(self, target: IO[bytes]) -> None:
        self._validate_current()
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
                remaining -= len(chunk)
            if source.read(1):
                raise ArtifactNamespaceError(
                    "Artifact changed while constructing the download"
                )
        self._validate_current()

    def _validate_current(self) -> None:
        metadata = os.fstat(self.fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink > 1
            or metadata.st_dev != self.device
            or metadata.st_ino != self.inode
            or metadata.st_size != self.size
        ):
            raise ArtifactNamespaceError(
                "Artifact changed while constructing the download"
            )


__all__ = ["ArtifactNamespaceError", "ManifestArtifact"]
