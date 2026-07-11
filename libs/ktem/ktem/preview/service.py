from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .context import PageContext, PreviewPurpose
from .errors import (
    PreviewContextError,
    PreviewConversionError,
    PreviewError,
    PreviewErrorCode,
)
from .models import PreviewSourceKind
from .source import classify_preview_source, is_valid_pdf

if TYPE_CHECKING:
    from .pdf import PdfPage, PdfService


class _OfficeConverter(Protocol):
    cache_dir: Path

    def convert_to_pdf(
        self, file_path: str | Path, file_name: str | None = None
    ) -> Path:
        ...

    def get_cached_pdf(
        self, file_path: str | Path, file_name: str | None = None
    ) -> Path | None:
        ...


def canonical_office_cache_dir() -> Path:
    configured = os.environ.get("KH_OFFICE_PDF_CACHE_DIR")
    if configured:
        return normalize_cache_root(Path(configured))
    app_data = os.environ.get("KH_APP_DATA_DIR")
    if app_data:
        return normalize_cache_root(Path(app_data) / "office_pdf_cache_dir")

    from theflow.settings import settings as flowsettings

    configured = getattr(flowsettings, "KH_OFFICE_PDF_CACHE_DIR", None)
    if configured:
        return normalize_cache_root(Path(configured))
    app_data = getattr(flowsettings, "KH_APP_DATA_DIR", None)
    if app_data:
        return normalize_cache_root(Path(app_data) / "office_pdf_cache_dir")
    return normalize_cache_root(
        Path(tempfile.gettempdir()) / "kotaemon_office_pdf_cache"
    )


def get_preview_cache_dir() -> Path:
    root = Path(os.environ.get("GRADIO_TEMP_DIR", tempfile.gettempdir()))
    return normalize_cache_root(root / "pdf_previews")


def publish_validated_pdf(
    source_path: str | Path,
    trusted_root: str | Path,
    entry: str | Path,
) -> Path:
    source = _regular_source_path(source_path)
    if not is_valid_pdf(source):
        raise _artifact_error(source, "The source artifact is not a valid PDF.")
    root = normalize_cache_root(Path(trusted_root))
    target = _trusted_target(root, Path(entry), source)
    if source == target:
        return target
    if target.is_file() and is_valid_pdf(target) and _same_artifact(source, target):
        return target

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        if not is_valid_pdf(temporary):
            raise _artifact_error(source, "The copied artifact is not a valid PDF.")
        os.replace(temporary, target)
    except PreviewError:
        raise
    except OSError as exc:
        raise _artifact_error(
            source, f"Unable to publish the PDF artifact: {exc}"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)
    return target


class OfficePreviewStore:
    """Expose canonical conversion artifacts at the legacy visible cache path."""

    def __init__(self, converter: _OfficeConverter, visible_dir: str | Path) -> None:
        self.converter = converter
        self.visible_dir = normalize_cache_root(Path(visible_dir))

    def convert(self, file_path: str | Path, file_name: str | None = None) -> Path:
        canonical = self.converter.convert_to_pdf(file_path, file_name)
        return self._visible_artifact(canonical)

    def get_cached(
        self, file_path: str | Path, file_name: str | None = None
    ) -> Path | None:
        canonical = self.converter.get_cached_pdf(file_path, file_name)
        if canonical is None:
            return None
        return self._visible_artifact(canonical)

    def _visible_artifact(self, canonical: Path) -> Path:
        return publish_validated_pdf(canonical, self.visible_dir, canonical.name)


class PreviewService:
    """UI-independent PDF preparation and consumer page-context policy."""

    def __init__(
        self,
        *,
        office: _OfficeConverter | None = None,
        pdf: PdfService | None = None,
        office_cache_dir: str | Path | None = None,
    ) -> None:
        if office is None:
            from .office import OfficeConversionService

            office = OfficeConversionService(
                office_cache_dir or canonical_office_cache_dir()
            )
        if pdf is None:
            from .pdf import PdfService

            pdf = PdfService()
        self.office = office
        self.pdf = pdf

    def prepare_pdf(
        self,
        file_path: str | Path,
        file_name: str | None = None,
        *,
        purpose: PreviewPurpose,
    ) -> Path | None:
        try:
            return self._prepare_pdf_strict(file_path, file_name)
        except PreviewError:
            if purpose is PreviewPurpose.WEB:
                return None
            raise

    def page_context(
        self,
        file_path: str | Path,
        file_name: str,
        page: int,
        *,
        purpose: PreviewPurpose,
        max_chars: int = 7000,
        fallback_text: str = "",
    ) -> PageContext:
        source_path = Path(file_path).expanduser().resolve()
        diagnostic: PreviewError | None = None
        pdf_page: PdfPage | None = None
        try:
            pdf_path = self._prepare_pdf_strict(source_path, file_name)
            pdf_page = self.pdf.page(pdf_path, page, max_chars=max_chars)
        except PreviewError as exc:
            if purpose in {PreviewPurpose.INDEXING, PreviewPurpose.ACCEPTANCE}:
                raise
            diagnostic = exc

        normalized_fallback = " ".join(str(fallback_text or "").split())[:max_chars]
        if pdf_page is not None and pdf_page.text:
            return _page_context(source_path, pdf_page, file_name, purpose)
        if normalized_fallback:
            return _fallback_context(
                source_path,
                file_name,
                page,
                purpose,
                normalized_fallback,
                diagnostic,
                pdf_page,
            )
        if purpose is PreviewPurpose.DOCQA:
            raise _context_error(source_path, diagnostic)
        if pdf_page is not None:
            return _page_context(source_path, pdf_page, file_name, purpose)
        return _fallback_context(
            source_path, file_name, page, purpose, "", diagnostic, None
        )

    def _prepare_pdf_strict(self, file_path: str | Path, file_name: str | None) -> Path:
        source = classify_preview_source(file_path, file_name=file_name)
        if source.kind is PreviewSourceKind.PDF:
            self.pdf.page_count(source.path)
            return source.path
        return self.office.convert_to_pdf(source.cache_path, file_name)


def _page_context(
    source_path: Path,
    page: PdfPage,
    file_name: str,
    purpose: PreviewPurpose,
) -> PageContext:
    return PageContext(
        source_path=source_path,
        file_name=file_name,
        purpose=purpose,
        page=page.page,
        total_pages=page.total_pages,
        text=page.text,
        pdf_path=page.path,
    )


def _fallback_context(
    source_path: Path,
    file_name: str,
    requested_page: int,
    purpose: PreviewPurpose,
    text: str,
    diagnostic: PreviewError | None,
    pdf_page: PdfPage | None,
) -> PageContext:
    return PageContext(
        source_path=source_path,
        file_name=file_name,
        purpose=purpose,
        page=pdf_page.page
        if pdf_page is not None
        else max(1, int(requested_page or 1)),
        total_pages=pdf_page.total_pages if pdf_page is not None else 1,
        text=text,
        pdf_path=pdf_page.path if pdf_page is not None else None,
        used_text_fallback=bool(text),
        diagnostic=diagnostic,
    )


def _context_error(
    source_path: Path,
    diagnostic: PreviewError | None,
) -> PreviewContextError:
    prior = f" Preview diagnostic: {diagnostic}" if diagnostic is not None else ""
    return PreviewContextError(
        PreviewErrorCode.CONTEXT_TEXT_UNAVAILABLE,
        stage="page_context",
        source_path=source_path,
        converter="preview",
        details=f"No text is available for the requested DocQA page.{prior}",
    )


def _artifact_error(source: Path, details: str) -> PreviewConversionError:
    return PreviewConversionError(
        PreviewErrorCode.OUTPUT_INVALID,
        stage="artifact_publish",
        source_path=source,
        converter="filesystem",
        details=details,
    )


def normalize_cache_root(path: Path) -> Path:
    normalized = Path(os.path.abspath(os.fspath(path.expanduser())))
    normalized.mkdir(parents=True, exist_ok=True)
    mode = normalized.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise _artifact_error(normalized, "The trusted cache root cannot be a symlink.")
    if not stat.S_ISDIR(mode):
        raise _artifact_error(normalized, "The trusted cache root is not a directory.")
    return normalized


def _regular_source_path(source_path: str | Path) -> Path:
    source = Path(os.path.abspath(os.fspath(Path(source_path).expanduser())))
    try:
        mode = source.lstat().st_mode
    except OSError as exc:
        raise _artifact_error(
            source, f"Unable to inspect the source artifact: {exc}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _artifact_error(source, "The source artifact must be a regular file.")
    return source


def _trusted_target(root: Path, entry: Path, source: Path) -> Path:
    if entry.is_absolute() or not entry.parts or ".." in entry.parts:
        raise _artifact_error(
            source, "The artifact entry must stay in the trusted cache root."
        )
    parent = root
    for part in entry.parts[:-1]:
        if part in {"", "."}:
            continue
        parent = parent / part
        if parent.is_symlink():
            raise _artifact_error(source, f"Artifact parent {parent} is a symlink.")
        parent.mkdir(exist_ok=True)
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise _artifact_error(
                source, f"Artifact parent {parent} is not a directory."
            )
    target = parent / entry.name
    if target.is_symlink():
        raise _artifact_error(source, f"Artifact target {target} is a symlink.")
    if target.exists() and not stat.S_ISREG(target.lstat().st_mode):
        raise _artifact_error(
            source, f"Artifact target {target} is not a regular file."
        )
    return target


def _same_artifact(source: Path, target: Path) -> bool:
    return _file_digest(source) == _file_digest(target)


def _file_digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for block in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()
