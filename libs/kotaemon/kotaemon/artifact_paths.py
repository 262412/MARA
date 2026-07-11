from __future__ import annotations

from pathlib import PurePosixPath


def portable_member_key(value: str | PurePosixPath) -> str:
    """Return the case/space-insensitive key used for portable ZIP members."""

    path = value if isinstance(value, PurePosixPath) else PurePosixPath(value)
    return "/".join(part.rstrip(" .").casefold() for part in path.parts)


__all__ = ["portable_member_key"]
