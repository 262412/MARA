from __future__ import annotations

import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

from .artifact_types import ArtifactNamespaceError


def portable_member_key(value: str | PurePosixPath) -> str:
    """Return the case/space-insensitive key used for portable ZIP members."""

    path = value if isinstance(value, PurePosixPath) else PurePosixPath(value)
    return "/".join(
        unicodedata.normalize("NFC", part.rstrip(" .")).casefold()
        for part in path.parts
    )


def validate_portable_component(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if (
        not value
        or value in {".", ".."}
        or normalized != value
        or value.rstrip(" .") != value
        or "/" in value
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or PureWindowsPath(value).is_reserved()
    ):
        raise ArtifactNamespaceError("Invalid artifact path component")
    return value


__all__ = ["portable_member_key", "validate_portable_component"]
