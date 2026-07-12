from __future__ import annotations

import re

from .artifact_paths import validate_portable_component
from .artifact_types import ArtifactNamespaceError

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")


def namespace_token(value: object) -> str:
    token = str(value or "")
    if token in {".", ".."} or _TOKEN_PATTERN.fullmatch(token) is None:
        raise ArtifactNamespaceError("Invalid artifact namespace identifier")
    return token


def safe_file_name(value: object) -> str:
    name = str(value or "")
    try:
        return validate_portable_component(name)
    except ArtifactNamespaceError as exc:
        raise ArtifactNamespaceError("Invalid artifact output name") from exc


__all__ = ["namespace_token", "safe_file_name"]
