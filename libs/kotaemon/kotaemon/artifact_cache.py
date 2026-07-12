from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from kotaemon.base import Document


class ArtifactDocuments(list[Document]):
    """Parser documents accompanied by an internal artifact-cache sidecar."""

    def __init__(
        self,
        documents: Iterable[Document],
        *,
        artifact_sidecar: dict[str, Any],
    ) -> None:
        super().__init__(documents)
        self.artifact_sidecar = artifact_sidecar


__all__ = ["ArtifactDocuments"]
