from __future__ import annotations

import logging
from pathlib import Path

from ktem.preview.office import OfficeConversionService
from ktem.preview.service import canonical_office_cache_dir
from ktem.preview.source import OFFICE_EXTENSIONS as _OFFICE_EXTENSIONS
from ktem.preview.source import detect_office_extension as _detect_office_extension
from ktem.preview.source import is_valid_pdf as _is_valid_pdf
from ktem.preview.source import legacy_preview_cache_signature

from .dependencies import find_soffice_binary

OFFICE_EXTENSIONS = _OFFICE_EXTENSIONS
LAYOUT_PRESERVING_OFFICE_EXTENSIONS = {".docx", ".doc"}


def detect_office_extension(file_name: str, file_path: str) -> str:
    return _detect_office_extension(file_name, file_path)


def get_file_signature(file_path: str | Path) -> str:
    return legacy_preview_cache_signature(file_path)


def is_valid_pdf(pdf_path: str | Path) -> bool:
    return _is_valid_pdf(pdf_path)


def get_office_pdf_cache_dir() -> Path:
    return canonical_office_cache_dir()


class OfficeToPdfConversionService:
    """Compatibility façade for strict layout-preserving Office conversion."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else get_office_pdf_cache_dir()
        self._core = OfficeConversionService(
            self.cache_dir,
            logger=logger,
            soffice_finder=lambda: find_soffice_binary(),
        )
        self._cache = self._core.cache

    def convert_to_pdf(
        self,
        file_path: str | Path,
        file_name: str | None = None,
    ) -> str:
        return str(self._core.convert_to_pdf(file_path, file_name))
