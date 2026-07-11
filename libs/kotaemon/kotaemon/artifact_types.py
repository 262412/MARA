from __future__ import annotations

import os
from dataclasses import dataclass
from typing import BinaryIO


class ArtifactNamespaceError(ValueError):
    """Raised when an artifact namespace or manifest is unsafe."""


@dataclass(frozen=True)
class ManifestArtifact:
    """A validated artifact held open across archive construction."""

    fd: int
    archive_name: str
    size: int

    def open(self) -> BinaryIO:
        return os.fdopen(os.dup(self.fd), "rb")

    def close(self) -> None:
        os.close(self.fd)


__all__ = ["ArtifactNamespaceError", "ManifestArtifact"]
