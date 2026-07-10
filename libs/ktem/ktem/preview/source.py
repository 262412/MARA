from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from struct import error as StructError
from struct import unpack_from
from typing import BinaryIO

from .errors import PreviewErrorCode, PreviewSourceError
from .models import ArchiveLimits, PreviewSource, PreviewSourceKind

OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}
OOXML_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
CFB_EXTENSIONS = {".doc", ".ppt", ".xls"}
OOXML_MARKERS = {
    "word/document.xml": ".docx",
    "ppt/presentation.xml": ".pptx",
    "xl/workbook.xml": ".xlsx",
}
CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_CFB_FREE_SECTOR = 0xFFFFFFFF
_CFB_END_OF_CHAIN = 0xFFFFFFFE
_CFB_FAT_SECTOR = 0xFFFFFFFD
_CFB_DIFAT_SECTOR = 0xFFFFFFFC
_CFB_STREAM_EXTENSIONS = {
    "WordDocument": ".doc",
    "PowerPoint Document": ".ppt",
    "Workbook": ".xls",
    "Book": ".xls",
}


def source_signature(file_path: str | Path) -> str:
    path = Path(file_path).expanduser()
    try:
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        raw = str(path.resolve())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def legacy_preview_cache_signature(file_path: str | Path) -> str:
    """Retain the established metadata digest used in preview cache filenames."""
    path_text = os.path.abspath(os.fspath(file_path))
    try:
        stat = os.stat(file_path)
        raw = f"{path_text}|{stat.st_size}|{int(stat.st_mtime_ns)}"
    except OSError:
        raw = path_text
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def classify_preview_source(
    file_path: str | Path,
    *,
    file_name: str | None = None,
    archive_limits: ArchiveLimits | None = None,
) -> PreviewSource:
    input_path = Path(file_path).expanduser()
    cache_path = Path(os.path.abspath(os.fspath(input_path)))
    path = input_path.resolve()
    if not path.is_file():
        raise _source_error(
            PreviewErrorCode.SOURCE_MISSING,
            path,
            "source_classification",
            "Verify that the source file exists and is a regular file.",
        )

    declared = Path(file_name or path.name).suffix.lower()
    kind, detected = _classify_signature(
        path,
        declared,
        archive_limits or ArchiveLimits(),
    )
    _validate_declared_type(path, declared, detected)
    return PreviewSource(
        path=path,
        cache_path=cache_path,
        kind=kind,
        extension=detected,
        signature=source_signature(path),
    )


def detect_office_extension(file_name: str, file_path: str) -> str:
    declared = Path(file_name or file_path or "").suffix.lower()
    if declared in OFFICE_EXTENSIONS:
        return declared
    if not file_path or not Path(file_path).is_file():
        return ""
    try:
        source = classify_preview_source(file_path, file_name=file_name or None)
    except PreviewSourceError:
        return ""
    return source.extension if source.extension in OFFICE_EXTENSIONS else ""


def is_office_source(file_name: str, file_path: str) -> bool:
    return bool(detect_office_extension(file_name, file_path))


def is_valid_pdf(file_path: str | Path) -> bool:
    path = Path(file_path)
    if not path.is_file():
        return False
    try:
        _validate_pdf(path)
    except PreviewSourceError:
        return False
    return True


def _classify_signature(
    path: Path,
    declared: str,
    limits: ArchiveLimits,
) -> tuple[PreviewSourceKind, str]:
    try:
        with path.open("rb") as file_obj:
            header = file_obj.read(8)
    except OSError as exc:
        raise _source_error(
            PreviewErrorCode.SOURCE_INVALID,
            path,
            "source_classification",
            f"Unable to read the source file: {exc}",
        ) from exc

    if header.startswith(b"%PDF-"):
        _validate_pdf(path)
        return PreviewSourceKind.PDF, ".pdf"
    if header.startswith(b"PK"):
        return PreviewSourceKind.OOXML, _inspect_ooxml_archive(path, limits)
    if header.startswith(CFB_SIGNATURE):
        return PreviewSourceKind.CFB, _inspect_cfb(path)
    if declared in OOXML_EXTENSIONS:
        return PreviewSourceKind.OOXML, _inspect_ooxml_archive(path, limits)
    if declared == ".pdf":
        _validate_pdf(path)
    raise _source_error(
        PreviewErrorCode.SOURCE_INVALID,
        path,
        "source_classification",
        "The file signature is not a supported PDF or Office document.",
    )


def _inspect_ooxml_archive(path: Path, limits: ArchiveLimits) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            _validate_archive_limits(path, infos, limits)
            damaged_member = archive.testzip()
            if damaged_member:
                raise _source_error(
                    PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
                    path,
                    "archive_validation",
                    f"The OOXML archive has a corrupt member: {damaged_member}.",
                )
            names = {info.filename for info in infos}
    except PreviewSourceError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise _source_error(
            PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
            path,
            "archive_validation",
            f"The OOXML archive cannot be read safely: {exc}",
        ) from exc

    detected = next(
        (ext for marker, ext in OOXML_MARKERS.items() if marker in names), ""
    )
    if detected:
        return detected
    raise _source_error(
        PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
        path,
        "archive_validation",
        "The archive is missing its Word, PowerPoint, or Excel package marker.",
    )


def _validate_archive_limits(
    path: Path,
    infos: list[zipfile.ZipInfo],
    limits: ArchiveLimits,
) -> None:
    if len(infos) > limits.max_entries:
        raise _source_error(
            PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
            path,
            "archive_validation",
            f"The OOXML archive exceeds the {limits.max_entries} entry limit.",
        )
    total_size = sum(max(0, info.file_size) for info in infos)
    if total_size > limits.max_uncompressed_bytes:
        raise _source_error(
            PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
            path,
            "archive_validation",
            "The OOXML archive exceeds the configured uncompressed size limit.",
        )
    for info in infos:
        ratio = info.file_size / max(1, info.compress_size)
        if ratio > limits.max_compression_ratio:
            raise _source_error(
                PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
                path,
                "archive_validation",
                f"Archive member {info.filename!r} exceeds the compression ratio limit.",
            )


def _validate_pdf(path: Path) -> None:
    try:
        from pypdf import PdfReader

        if not PdfReader(str(path), strict=False).pages:
            raise ValueError("the PDF has no pages")
    except Exception as exc:
        raise _source_error(
            PreviewErrorCode.SOURCE_INVALID,
            path,
            "pdf_validation",
            f"The PDF cannot be parsed and previewed: {exc}",
        ) from exc


def _inspect_cfb(path: Path) -> str:
    try:
        with path.open("rb") as file_obj:
            header = file_obj.read(512)
            layout = _read_cfb_layout(file_obj, header, path.stat().st_size)
            sector_size, total_sectors, first_directory, fat_sector_ids = layout
            fat = _read_cfb_fat(
                file_obj,
                sector_size,
                total_sectors,
                fat_sector_ids,
            )
            stream_names = _read_cfb_directory_streams(
                file_obj,
                sector_size,
                total_sectors,
                first_directory,
                fat,
            )
    except PreviewSourceError:
        raise
    except (OSError, ValueError, UnicodeError, StructError) as exc:
        raise _cfb_error(path, f"The compound file cannot be parsed: {exc}") from exc

    extensions = {
        extension
        for name, extension in _CFB_STREAM_EXTENSIONS.items()
        if name in stream_names
    }
    if len(extensions) == 1:
        return extensions.pop()
    if not extensions:
        raise _cfb_error(
            path,
            "The compound file has no recognized Office document stream.",
        )
    raise _cfb_error(
        path,
        "The compound file contains conflicting Office document streams.",
    )


def _read_cfb_layout(
    file_obj: BinaryIO,
    header: bytes,
    file_size: int,
) -> tuple[int, int, int, list[int]]:
    if len(header) != 512 or not header.startswith(CFB_SIGNATURE):
        raise ValueError("invalid compound file header")
    major_version, byte_order, sector_shift = unpack_from("<HHH", header, 26)
    expected_shift = {3: 9, 4: 12}.get(major_version)
    if byte_order != 0xFFFE or expected_shift != sector_shift:
        raise ValueError("invalid compound file byte order or sector size")
    sector_size = 1 << sector_shift
    if file_size < 3 * sector_size or file_size % sector_size:
        raise ValueError("invalid compound file sector layout")
    total_sectors = file_size // sector_size - 1
    fat_sector_count = unpack_from("<I", header, 44)[0]
    first_directory = unpack_from("<I", header, 48)[0]
    if not 1 <= fat_sector_count <= total_sectors:
        raise ValueError("invalid compound file FAT sector count")
    if first_directory >= total_sectors:
        raise ValueError("invalid compound file directory sector")
    fat_sector_ids = _read_cfb_difat(
        file_obj,
        header,
        sector_size,
        total_sectors,
    )
    if len(fat_sector_ids) < fat_sector_count:
        raise ValueError("compound file DIFAT is incomplete")
    return (
        sector_size,
        total_sectors,
        first_directory,
        fat_sector_ids[:fat_sector_count],
    )


def _read_cfb_difat(
    file_obj: BinaryIO,
    header: bytes,
    sector_size: int,
    total_sectors: int,
) -> list[int]:
    fat_sector_ids = [
        unpack_from("<I", header, 76 + index * 4)[0] for index in range(109)
    ]
    fat_sector_ids = [sector for sector in fat_sector_ids if sector != _CFB_FREE_SECTOR]
    next_difat = unpack_from("<I", header, 68)[0]
    difat_count = unpack_from("<I", header, 72)[0]
    for _ in range(difat_count):
        sector = _read_cfb_sector(file_obj, next_difat, sector_size, total_sectors)
        entry_count = sector_size // 4
        values = [
            unpack_from("<I", sector, index * 4)[0] for index in range(entry_count)
        ]
        fat_sector_ids.extend(
            value for value in values[:-1] if value != _CFB_FREE_SECTOR
        )
        next_difat = values[-1]
    return fat_sector_ids


def _read_cfb_fat(
    file_obj: BinaryIO,
    sector_size: int,
    total_sectors: int,
    fat_sector_ids: list[int],
) -> list[int]:
    fat: list[int] = []
    for sector_id in fat_sector_ids:
        sector = _read_cfb_sector(file_obj, sector_id, sector_size, total_sectors)
        fat.extend(
            unpack_from("<I", sector, offset)[0] for offset in range(0, sector_size, 4)
        )
    if len(fat) < total_sectors:
        raise ValueError("compound file FAT is incomplete")
    return fat


def _read_cfb_directory_streams(
    file_obj: BinaryIO,
    sector_size: int,
    total_sectors: int,
    first_directory: int,
    fat: list[int],
) -> set[str]:
    streams: set[str] = set()
    visited: set[int] = set()
    sector_id = first_directory
    while sector_id != _CFB_END_OF_CHAIN:
        if sector_id in visited:
            raise ValueError("compound file directory chain contains a cycle")
        visited.add(sector_id)
        sector = _read_cfb_sector(file_obj, sector_id, sector_size, total_sectors)
        for offset in range(0, sector_size, 128):
            if sector[offset + 66] != 2:
                continue
            name_length = unpack_from("<H", sector, offset + 64)[0]
            if name_length < 2 or name_length > 64 or name_length % 2:
                raise ValueError("invalid compound file stream name")
            name_bytes = sector[offset : offset + name_length - 2]
            streams.add(name_bytes.decode("utf-16le"))
        if sector_id >= len(fat):
            raise ValueError("compound file directory is outside the FAT")
        sector_id = fat[sector_id]
        if sector_id in {
            _CFB_FREE_SECTOR,
            _CFB_FAT_SECTOR,
            _CFB_DIFAT_SECTOR,
        }:
            raise ValueError("invalid compound file directory chain marker")
    return streams


def _read_cfb_sector(
    file_obj: BinaryIO,
    sector_id: int,
    sector_size: int,
    total_sectors: int,
) -> bytes:
    if sector_id >= total_sectors:
        raise ValueError(f"compound file sector {sector_id} is out of range")
    file_obj.seek((sector_id + 1) * sector_size)
    sector = file_obj.read(sector_size)
    if len(sector) != sector_size:
        raise ValueError(f"compound file sector {sector_id} is truncated")
    return sector


def _cfb_error(path: Path, details: str) -> PreviewSourceError:
    return _source_error(
        PreviewErrorCode.SOURCE_INVALID,
        path,
        "cfb_validation",
        details,
    )


def _validate_declared_type(
    path: Path,
    declared: str,
    detected: str,
) -> None:
    if not declared or declared == detected:
        return
    raise _source_error(
        PreviewErrorCode.SOURCE_TYPE_MISMATCH,
        path,
        "source_classification",
        f"Declared type {declared!r} does not match detected type {detected!r}.",
    )


def _source_error(
    code: PreviewErrorCode,
    path: Path,
    stage: str,
    details: str,
) -> PreviewSourceError:
    return PreviewSourceError(
        code,
        stage=stage,
        source_path=path,
        converter="source",
        details=details,
    )
