from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .artifact_types import ArtifactNamespaceError

_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


def require_secure_dir_fd() -> None:
    required = (os.open, os.mkdir, os.stat, os.unlink)
    supported: set[object] = getattr(os, "supports_dir_fd", set())
    flags_available = hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")
    if (
        os.name != "posix"
        or not flags_available
        or any(function not in supported for function in required)
    ):
        raise ArtifactNamespaceError(
            "Secure artifact filesystem operations are unsupported on this platform"
        )


def open_directory_fd(
    root: str | Path,
    parts: Iterable[str] = (),
    *,
    create: bool,
) -> tuple[Path, int]:
    """Open a directory chain without following its configured or child symlinks."""

    require_secure_dir_fd()
    root_path = Path(root).expanduser().absolute()
    if create:
        try:
            root_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ArtifactNamespaceError("Artifact root unavailable") from exc
    root_fd = _open_root(root_path)
    current_fd = root_fd
    current_path = root_path
    try:
        for part in parts:
            _validate_component(part)
            next_fd = _open_child_directory(current_fd, part, create=create)
            os.close(current_fd)
            current_fd = next_fd
            current_path /= part
        return current_path, current_fd
    except BaseException:
        os.close(current_fd)
        raise


def open_regular_file(
    root: str | Path,
    parts: tuple[str, ...],
) -> tuple[int, os.stat_result]:
    if not parts:
        raise ArtifactNamespaceError("Artifact file path is empty")
    directory_path, directory_fd = open_directory_fd(root, parts[:-1], create=False)
    del directory_path
    try:
        _validate_component(parts[-1])
        fd = os.open(parts[-1], _FILE_FLAGS, dir_fd=directory_fd)
    except OSError as exc:
        raise ArtifactNamespaceError("Artifact file unavailable") from exc
    finally:
        os.close(directory_fd)
    try:
        metadata = os.fstat(fd)
        _validate_regular_metadata(metadata)
        return fd, metadata
    except BaseException:
        os.close(fd)
        raise


def list_regular_files(
    root: str | Path,
    parts: tuple[str, ...],
) -> list[tuple[str, os.stat_result]]:
    try:
        _path, directory_fd = open_directory_fd(root, parts, create=False)
    except ArtifactNamespaceError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return []
        raise
    try:
        result = []
        for name in sorted(os.listdir(directory_fd)):
            _validate_component(name)
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise ArtifactNamespaceError("Artifact file unavailable") from exc
            _validate_regular_metadata(metadata)
            result.append((name, metadata))
        return result
    finally:
        os.close(directory_fd)


def atomic_write_bytes(
    root: str | Path,
    directory_parts: tuple[str, ...],
    leaf_name: str,
    content: bytes,
) -> Path:
    directory_path, directory_fd = open_directory_fd(
        root,
        directory_parts,
        create=True,
    )
    try:
        atomic_write_at(directory_fd, leaf_name, content)
    finally:
        os.close(directory_fd)
    return directory_path / leaf_name


def atomic_write_at(directory_fd: int, leaf_name: str, content: bytes) -> None:
    _validate_component(leaf_name)
    temporary_name = f".artifact-{uuid4().hex}.tmp"
    temporary_fd = -1
    try:
        temporary_fd = create_exclusive_file_at(directory_fd, temporary_name)
        with os.fdopen(temporary_fd, "wb") as output:
            temporary_fd = -1
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        replace_at(directory_fd, temporary_name, leaf_name)
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)
        unlink_at(directory_fd, temporary_name)


def create_exclusive_file_at(directory_fd: int, name: str) -> int:
    _validate_component(name)
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        return os.open(name, flags, 0o600, dir_fd=directory_fd)
    except OSError as exc:
        raise ArtifactNamespaceError("Artifact temporary file unavailable") from exc


def replace_at(directory_fd: int, source: str, destination: str) -> None:
    _validate_component(source)
    _validate_component(destination)
    try:
        os.replace(
            source,
            destination,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    except (NotImplementedError, OSError, TypeError) as exc:
        raise ArtifactNamespaceError("Atomic artifact replacement failed") from exc


def unlink_at(directory_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ArtifactNamespaceError("Artifact temporary cleanup failed") from exc


def open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
    _validate_component(name)
    return _open_child_directory(parent_fd, name, create=create)


def _open_root(path: Path) -> int:
    try:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise ArtifactNamespaceError("Configured artifact root cannot be a symlink")
        fd = os.open(path, _DIRECTORY_FLAGS)
    except ArtifactNamespaceError:
        raise
    except OSError as exc:
        raise ArtifactNamespaceError("Artifact root unavailable") from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise ArtifactNamespaceError("Artifact root must be a directory")
    return fd


def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ArtifactNamespaceError("Artifact namespace unavailable") from exc
    try:
        return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError as exc:
        raise ArtifactNamespaceError("Artifact namespace unavailable") from exc
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            message = "Artifact directory symlinks are not allowed"
        else:
            message = "Artifact namespace unavailable"
        raise ArtifactNamespaceError(message) from exc


def _validate_regular_metadata(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise ArtifactNamespaceError("Artifact must be a regular file")
    if metadata.st_nlink != 1:
        raise ArtifactNamespaceError("Artifact hard links are not allowed")


def _validate_component(value: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ArtifactNamespaceError("Invalid artifact path component")


__all__ = [
    "atomic_write_at",
    "atomic_write_bytes",
    "create_exclusive_file_at",
    "list_regular_files",
    "open_child_directory",
    "open_directory_fd",
    "open_regular_file",
    "replace_at",
    "require_secure_dir_fd",
    "unlink_at",
]
