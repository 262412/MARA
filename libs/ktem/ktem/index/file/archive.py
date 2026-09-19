from __future__ import annotations

import logging
import os
import re
import shutil
import stat
import tempfile
import zipfile
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO

from kotaemon.artifact_paths import portable_member_key, validate_portable_component
from kotaemon.artifact_types import ArtifactNamespaceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _OwnedArchiveDirectory:
    path: Path
    identity: tuple[int, int]

    @classmethod
    def created(cls, path: Path):
        info = path.lstat()
        return cls(path, (info.st_dev, info.st_ino))

    def remove(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if (
            self.path.resolve() != self.path
            or (info.st_dev, info.st_ino) != self.identity
        ):
            raise OSError(f"Refusing changed ZIP input directory: {self.path}")
        pending = [self.path]
        while pending:
            path = pending.pop()
            info = path.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError(f"Refusing ZIP input link or reparse point: {path}")
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    pending.extend(Path(entry.path) for entry in entries)
        shutil.rmtree(self.path)


# Only synchronous preparation installs a collector. It is reset before any
# generator yield (Gradio can resume successive next() calls on other threads).
# Public extract/expand calls outside this scope retain ownership as before.
_owned_inputs: ContextVar[list[_OwnedArchiveDirectory] | None] = ContextVar(
    "owned_zip_inputs", default=None
)


class OwnedZipInputs:
    """Receipts for ZIP roots created by this preparation, never inferred paths."""

    def __init__(self) -> None:
        self._directories: list[_OwnedArchiveDirectory] = []

    def __enter__(self):
        return self

    def prepare(self, operation, *args, **kwargs):
        token = _owned_inputs.set(self._directories)
        try:
            return operation(*args, **kwargs)
        finally:
            _owned_inputs.reset(token)

    def __exit__(self, exc_type, primary, traceback) -> None:
        failure = None
        for receipt in reversed(self._directories):
            try:
                receipt.remove()
            except BaseException as exc:
                logger.exception(
                    "ZIP input cleanup failed: root=%s primary=%r",
                    receipt.path,
                    primary,
                )
                failure = failure or exc
        if failure is not None and primary is None:
            raise failure


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 2_000
    max_member_bytes: int = 512 * 1024 * 1024
    max_total_bytes: int = 2 * 1024 * 1024 * 1024
    max_compression_ratio: float = 1_000.0


DEFAULT_ARCHIVE_LIMITS = ArchiveLimits()


class ArchiveExtractionError(ValueError):
    def __init__(
        self,
        archive_path: str | Path,
        *,
        stage: str,
        reason: str,
        member: str | None = None,
    ) -> None:
        self.archive_path = Path(archive_path)
        self.stage = stage
        self.reason = reason
        self.member = member
        diagnostic = f"ZIP extraction failed: archive={self.archive_path} stage={stage}"
        if member is not None:
            diagnostic += f" member={member}"
        super().__init__(f"{diagnostic} reason={reason}")


@dataclass(frozen=True)
class _ValidatedMember:
    info: zipfile.ZipInfo
    relative_path: PurePosixPath


def extract_supported_zip_files(
    archive_path: str | Path,
    *,
    destination_parent: str | Path,
    supported_types: set[str],
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> list[str]:
    archive = Path(archive_path)
    normalized_types = {
        extension.strip().lower()
        for extension in supported_types
        if extension.strip() and extension.strip().lower() != ".zip"
    }
    try:
        with zipfile.ZipFile(archive, "r") as zip_file:
            members = _validate_members(archive, zip_file.infolist(), limits)
            _verify_members(archive, zip_file, members, limits)
            selected = sorted(
                (
                    member
                    for member in members
                    if member.relative_path.suffix.lower() in normalized_types
                ),
                key=lambda member: member.relative_path.as_posix(),
            )
            if not selected:
                return []
            return _extract_members(
                archive,
                zip_file,
                selected,
                Path(destination_parent),
                limits,
            )
    except ArchiveExtractionError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ArchiveExtractionError(
            archive,
            stage="open",
            reason=str(exc),
        ) from exc


def _validate_members(
    archive: Path,
    infos: list[zipfile.ZipInfo],
    limits: ArchiveLimits,
) -> list[_ValidatedMember]:
    if len(infos) > limits.max_members:
        raise ArchiveExtractionError(
            archive,
            stage="validate-archive",
            reason=f"members {len(infos)} exceed limit {limits.max_members}",
        )

    validated: list[_ValidatedMember] = []
    seen_paths: set[str] = set()
    total_bytes = 0
    for info in infos:
        relative_path = _validate_member_path(archive, info)
        _validate_member_type(archive, info)
        _validate_member_size(archive, info, limits)
        total_bytes += info.file_size
        if total_bytes > limits.max_total_bytes:
            raise ArchiveExtractionError(
                archive,
                stage="validate-archive",
                reason=(
                    f"total size {total_bytes} exceeds limit "
                    f"{limits.max_total_bytes}"
                ),
                member=info.filename,
            )
        normalized = _portable_member_key(relative_path)
        if normalized in seen_paths:
            raise ArchiveExtractionError(
                archive,
                stage="validate-member",
                reason="duplicate normalized member path",
                member=info.filename,
            )
        seen_paths.add(normalized)
        _validate_portable_member_path(archive, info, relative_path)
        if not info.is_dir():
            validated.append(_ValidatedMember(info, relative_path))
    return validated


def _validate_member_path(archive: Path, info: zipfile.ZipInfo) -> PurePosixPath:
    raw_name = info.filename
    normalized_name = raw_name.replace("\\", "/")
    relative_path = PurePosixPath(normalized_name)
    has_drive = any(":" in part for part in relative_path.parts)
    has_reserved_name = any(
        PureWindowsPath(part).is_reserved() for part in relative_path.parts
    )
    if (
        not normalized_name
        or "\x00" in normalized_name
        or normalized_name.startswith("/")
        or has_drive
        or has_reserved_name
        or any(part == ".." for part in relative_path.parts)
        or any(not part.rstrip(" .") for part in relative_path.parts)
    ):
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason=(
                "member path is absolute, reserved, or escapes the extraction "
                "directory"
            ),
            member=raw_name,
        )
    if not any(part not in {"", "."} for part in relative_path.parts):
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="member path is empty",
            member=raw_name,
        )
    return relative_path


def _validate_portable_member_path(
    archive: Path,
    info: zipfile.ZipInfo,
    relative_path: PurePosixPath,
) -> None:
    try:
        for part in relative_path.parts:
            validate_portable_component(part)
    except ArtifactNamespaceError as exc:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="member path is not portable",
            member=info.filename,
        ) from exc


def _portable_member_key(relative_path: PurePosixPath) -> str:
    return portable_member_key(relative_path)


def _validate_member_type(archive: Path, info: zipfile.ZipInfo) -> None:
    if info.flag_bits & 0x1:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="encrypted members are not supported",
            member=info.filename,
        )
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if file_type == stat.S_IFLNK:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="symbolic link members are not allowed",
            member=info.filename,
        )
    if file_type == stat.S_IFDIR and not info.is_dir():
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="directory type does not match the member path",
            member=info.filename,
        )
    if info.is_dir() and file_type not in {0, stat.S_IFDIR}:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="directory member is not marked as a directory",
            member=info.filename,
        )
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason="non-regular member type is not allowed",
            member=info.filename,
        )


def _validate_member_size(
    archive: Path,
    info: zipfile.ZipInfo,
    limits: ArchiveLimits,
) -> None:
    if info.file_size > limits.max_member_bytes:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason=(
                f"member size {info.file_size} exceeds limit "
                f"{limits.max_member_bytes}"
            ),
            member=info.filename,
        )
    ratio = info.file_size / max(info.compress_size, 1)
    if ratio > limits.max_compression_ratio:
        raise ArchiveExtractionError(
            archive,
            stage="validate-member",
            reason=(
                f"compression ratio {ratio:.1f} exceeds limit "
                f"{limits.max_compression_ratio:.1f}"
            ),
            member=info.filename,
        )


def _extract_members(
    archive: Path,
    zip_file: zipfile.ZipFile,
    members: list[_ValidatedMember],
    destination_parent: Path,
    limits: ArchiveLimits,
) -> list[str]:
    try:
        destination_parent.mkdir(parents=True, exist_ok=True)
        prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", archive.stem) or "archive"
        output_dir = Path(
            tempfile.mkdtemp(dir=destination_parent, prefix=f"{prefix}_")
        ).resolve()
        receipt = _OwnedArchiveDirectory.created(output_dir)
        if (owned := _owned_inputs.get()) is not None:
            owned.append(receipt)
    except OSError as exc:
        raise ArchiveExtractionError(
            archive,
            stage="prepare-output",
            reason=str(exc),
        ) from exc
    extracted: list[str] = []
    current_member: str | None = None
    try:
        for member in members:
            current_member = member.info.filename
            output_path = output_dir.joinpath(*member.relative_path.parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with (
                zip_file.open(member.info, "r") as source,
                output_path.open("xb") as target,
            ):
                copied = _copy_member(source, target, limits.max_member_bytes)
            if copied != member.info.file_size:
                raise ValueError(
                    f"extracted size {copied} does not match declared size "
                    f"{member.info.file_size}"
                )
            extracted.append(str(output_path.resolve()))
    except BaseException as exc:
        try:
            receipt.remove()
        except BaseException:
            logger.exception(
                "ZIP extraction cleanup failed: root=%s primary=%r", output_dir, exc
            )
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, ArchiveExtractionError):
            raise
        raise ArchiveExtractionError(
            archive,
            stage="extract-member",
            reason=str(exc),
            member=current_member,
        ) from exc
    return extracted


def _verify_members(
    archive: Path,
    zip_file: zipfile.ZipFile,
    members: list[_ValidatedMember],
    limits: ArchiveLimits,
) -> None:
    total_bytes = 0
    for member in members:
        try:
            with zip_file.open(member.info, "r") as source:
                copied = _copy_member(source, None, limits.max_member_bytes)
            if copied != member.info.file_size:
                raise ValueError(
                    f"verified size {copied} does not match declared size "
                    f"{member.info.file_size}"
                )
            total_bytes += copied
            if total_bytes > limits.max_total_bytes:
                raise ValueError(
                    f"verified total size {total_bytes} exceeds limit "
                    f"{limits.max_total_bytes}"
                )
        except Exception as exc:
            raise ArchiveExtractionError(
                archive,
                stage="verify-member",
                reason=str(exc),
                member=member.info.filename,
            ) from exc


def _copy_member(
    source: IO[bytes],
    target: IO[bytes] | None,
    byte_limit: int,
) -> int:
    copied = 0
    while chunk := source.read(min(1024 * 1024, byte_limit + 1 - copied)):
        copied += len(chunk)
        if copied > byte_limit:
            raise ValueError(f"extracted member exceeds byte limit {byte_limit}")
        if target is not None:
            target.write(chunk)
    return copied


__all__ = [
    "ArchiveExtractionError",
    "ArchiveLimits",
    "DEFAULT_ARCHIVE_LIMITS",
    "extract_supported_zip_files",
]
