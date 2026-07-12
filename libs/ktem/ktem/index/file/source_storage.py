"""Atomic publication and relational registration of uploaded source files."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from .storage_lifetime import StorageLifetime


def store_source_file(
    file_path: Path,
    *,
    storage_root: str | Path,
    source_table: Any,
    user_id: Any,
    session_factory: Callable[[], Session],
    storage_lifetime: Any | None = None,
) -> str:
    """Publish content and commit its Source row under one shared-path lock."""
    with file_path.open("rb") as input_file:
        file_hash = sha256(input_file.read()).hexdigest()

    lifetime = storage_lifetime or StorageLifetime(storage_root)
    with lifetime.hold(file_hash) as lease:
        lease.publish_from(file_path)
        source = source_table(
            name=file_path.name,
            path=file_hash,
            size=file_path.stat().st_size,
            user=user_id,
        )
        with session_factory() as session:
            session.add(source)
            session.commit()
            file_id = source.id
    return str(file_id)


__all__ = ["store_source_file"]
