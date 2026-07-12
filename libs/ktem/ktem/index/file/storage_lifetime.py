"""Cross-process lifetime control for content-addressed source files."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Protocol

from filelock import FileLock


class _Lock(Protocol):
    def __enter__(self) -> object:
        ...

    def __exit__(self, *args: object) -> object:
        ...


class StorageLifetimeError(ValueError):
    """A stored path or filesystem object violates the lifetime contract."""


@dataclass(frozen=True)
class QuarantineMove:
    """A reversible move made while a storage-path lock is held."""

    original: Path
    quarantine: Path


class StorageLease:
    """Operations permitted while one stored-path lock is held."""

    def __init__(
        self,
        root: Path,
        target: Path,
        mover: Callable[[Path, Path], None],
        unlinker: Callable[[Path], None],
        directory_syncer: Callable[[Path], None],
    ) -> None:
        self._root = root
        self._target = target
        self._mover = mover
        self._unlinker = unlinker
        self._directory_syncer = directory_syncer

    def publish_from(self, source: str | Path) -> None:
        """Atomically publish a regular file, accepting identical retries."""
        source_path = Path(source)
        _require_regular(source_path, "upload source")
        _ensure_target_parent(self._root, self._target)
        if _path_exists(self._target):
            _require_regular(self._target, "stored file")
            if _file_digest(source_path) != _file_digest(self._target):
                raise StorageLifetimeError("stored file has different content")
            return

        temporary = self._copy_to_temporary(source_path)
        try:
            self._mover(temporary, self._target)
            self._directory_syncer(self._target.parent)
        finally:
            if _path_exists(temporary):
                temporary.unlink()

    def quarantine(self) -> QuarantineMove | None:
        """Move the stored file aside so SQL can commit without losing rollback."""
        if not _path_exists(self._target):
            return None
        _require_regular(self._target, "stored file")
        quarantine = self._target.with_name(
            f".{self._target.name}.quarantine-{uuid.uuid4().hex}"
        )
        self._mover(self._target, quarantine)
        try:
            self._directory_syncer(self._target.parent)
        except Exception:
            self._mover(quarantine, self._target)
            self._directory_syncer(self._target.parent)
            raise
        return QuarantineMove(original=self._target, quarantine=quarantine)

    def restore(self, move: QuarantineMove) -> None:
        """Restore a quarantined file after a relational commit failure."""
        self._validate_move(move)
        if not _path_exists(move.quarantine):
            raise StorageLifetimeError("quarantined file is missing")
        _require_regular(move.quarantine, "quarantined file")
        if _path_exists(move.original):
            raise StorageLifetimeError("stored file already exists during restore")
        self._mover(move.quarantine, move.original)
        self._directory_syncer(move.original.parent)

    def purge(self, move: QuarantineMove) -> None:
        """Permanently remove a quarantined file after SQL commit."""
        self._validate_move(move)
        if not _path_exists(move.quarantine):
            return
        _require_regular(move.quarantine, "quarantined file")
        self._unlinker(move.quarantine)
        self._directory_syncer(move.quarantine.parent)

    def _copy_to_temporary(self, source: Path) -> Path:
        descriptor, raw_path = tempfile.mkstemp(
            dir=self._target.parent,
            prefix=f".{self._target.name}.tmp-",
        )
        temporary = Path(raw_path)
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
            return temporary
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _validate_move(self, move: QuarantineMove) -> None:
        if (
            move.original != self._target
            or move.quarantine.parent != self._target.parent
        ):
            raise StorageLifetimeError("quarantine move does not belong to this lease")


class StorageLifetime:
    """Create cross-process leases keyed by stored relative path."""

    def __init__(
        self,
        storage_root: str | Path,
        *,
        lock_factory: Callable[[str], _Lock] | None = None,
        mover: Callable[[Path, Path], None] | None = None,
        unlinker: Callable[[Path], None] | None = None,
        directory_syncer: Callable[[Path], None] | None = None,
    ) -> None:
        self._root = Path(storage_root)
        self._lock_factory = lock_factory or FileLock
        self._mover = mover or os.replace
        self._unlinker = unlinker or Path.unlink
        self._directory_syncer = directory_syncer or _fsync_directory

    @contextmanager
    def hold(self, stored_path: str | Path) -> Iterator[StorageLease]:
        """Hold the stable lock for a validated relative stored path."""
        relative = _validate_relative(stored_path)
        _ensure_root(self._root)
        lock_root = self._root / ".mara-locks"
        lock_root.mkdir(exist_ok=True)
        _ensure_real_directory(lock_root)
        lock_name = hashlib.sha256(os.fsencode(str(relative))).hexdigest() + ".lock"
        target = self._root.joinpath(relative)
        with self._lock_factory(str(lock_root / lock_name)):
            _validate_ancestors(self._root, target)
            yield StorageLease(
                self._root,
                target,
                self._mover,
                self._unlinker,
                self._directory_syncer,
            )


def _validate_relative(stored_path: str | Path) -> Path:
    relative = Path(stored_path)
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise StorageLifetimeError("stored path must stay inside the storage root")
    if relative == Path("."):
        raise StorageLifetimeError("stored path must identify a file")
    return relative


def _ensure_root(root: Path) -> None:
    if not _path_exists(root):
        root.mkdir(parents=True)
    _ensure_real_directory(root)


def _ensure_real_directory(path: Path) -> None:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise StorageLifetimeError(f"directory path is not a real directory: {path}")


def _validate_ancestors(root: Path, target: Path) -> None:
    current = root
    for part in target.relative_to(root).parts[:-1]:
        current = current / part
        if _path_exists(current):
            _ensure_real_directory(current)


def _ensure_target_parent(root: Path, target: Path) -> None:
    current = root
    for part in target.relative_to(root).parts[:-1]:
        current = current / part
        if not _path_exists(current):
            current.mkdir()
        _ensure_real_directory(current)


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _require_regular(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise StorageLifetimeError(f"{label} is missing") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise StorageLifetimeError(f"{label} must be a regular file")


def _file_digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "QuarantineMove",
    "StorageLease",
    "StorageLifetime",
    "StorageLifetimeError",
]
