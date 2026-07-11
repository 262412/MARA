from __future__ import annotations

import re

from .artifact_types import ArtifactNamespaceError

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")


def namespace_token(value: object) -> str:
    token = str(value or "")
    if token in {".", ".."} or _TOKEN_PATTERN.fullmatch(token) is None:
        raise ArtifactNamespaceError("Invalid artifact namespace identifier")
    return token


def safe_file_name(value: object) -> str:
    name = str(value or "")
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ArtifactNamespaceError("Invalid artifact output name")
    return name


__all__ = ["namespace_token", "safe_file_name"]
