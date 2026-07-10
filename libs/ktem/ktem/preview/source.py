from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from struct import unpack_from

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
    path = Path(file_path).expanduser().resolve()
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
    _validate_declared_type(path, declared, detected, kind)
    return PreviewSource(
        path=path,
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
        _validate_cfb(path)
        detected = declared if declared in CFB_EXTENSIONS else ".doc"
        return PreviewSourceKind.CFB, detected
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


def _validate_cfb(path: Path) -> None:
    try:
        with path.open("rb") as file_obj:
            header = file_obj.read(512)
        file_size = path.stat().st_size
    except OSError as exc:
        raise _source_error(
            PreviewErrorCode.SOURCE_INVALID,
            path,
            "cfb_validation",
            f"Unable to read the compound file header: {exc}",
        ) from exc

    valid = len(header) == 512 and header.startswith(CFB_SIGNATURE)
    if valid:
        major_version, byte_order, sector_shift = unpack_from("<HHH", header, 26)
        expected_shift = {3: 9, 4: 12}.get(major_version)
        sector_size = 1 << sector_shift if sector_shift < 16 else 0
        payload_size = file_size - 512
        fat_sectors = unpack_from("<I", header, 44)[0]
        first_directory_sector = unpack_from("<I", header, 48)[0]
        valid = bool(
            byte_order == 0xFFFE
            and expected_shift == sector_shift
            and sector_size
            and payload_size >= 2 * sector_size
            and payload_size % sector_size == 0
            and fat_sectors >= 1
            and first_directory_sector not in {0xFFFFFFFF, 0xFFFFFFFE}
        )
    if not valid:
        raise _source_error(
            PreviewErrorCode.SOURCE_INVALID,
            path,
            "cfb_validation",
            "The compound file header or sector layout is corrupt.",
        )


def _validate_declared_type(
    path: Path,
    declared: str,
    detected: str,
    kind: PreviewSourceKind,
) -> None:
    if not declared or declared == detected:
        return
    if kind is PreviewSourceKind.CFB and declared in CFB_EXTENSIONS:
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
