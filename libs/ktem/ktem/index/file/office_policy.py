from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ktem.preview.errors import PreviewConversionError, PreviewError, PreviewErrorCode

logger = logging.getLogger(__name__)


class OfficePdfConverter(Protocol):
    def convert_to_pdf(
        self, file_path: str | Path, file_name: str | None = None
    ) -> str:
        ...


def prepare_office_parse_file(
    file_path: Path,
    extension: str,
    *,
    converter: OfficePdfConverter,
    strict: bool,
    pdf_validator: Callable[[str | Path], bool],
) -> tuple[Path, dict]:
    conversion_error: PreviewError | None = None
    try:
        converted_pdf = converter.convert_to_pdf(file_path, file_path.name)
    except PreviewError as exc:
        if strict:
            raise
        conversion_error = exc
        converted_pdf = ""

    if converted_pdf and pdf_validator(converted_pdf):
        converted_path = Path(converted_pdf).resolve()
        return converted_path, _conversion_metadata(
            file_path, extension, converted_path
        )

    if conversion_error is None:
        conversion_error = _missing_or_invalid_output(file_path, bool(converted_pdf))
    if strict:
        raise conversion_error

    message = str(conversion_error)
    logger.warning("Non-strict Office indexing fallback: %s", message)
    return file_path, {
        "source_file_name": file_path.name,
        "source_file_path": str(file_path),
        "source_file_extension": extension,
        "converted_from_office": False,
        "layout_preserving_parse": False,
        "direct_office_text_fallback": extension == ".docx",
        "office_pdf_conversion_error": message,
    }


def _conversion_metadata(
    file_path: Path,
    extension: str,
    converted_path: Path,
) -> dict:
    return {
        "source_file_name": file_path.name,
        "source_file_path": str(file_path),
        "source_file_extension": extension,
        "converted_from_office": True,
        "converted_pdf_path": str(converted_path),
        "layout_preserving_parse": True,
    }


def _missing_or_invalid_output(
    file_path: Path,
    output_exists: bool,
) -> PreviewConversionError:
    code = (
        PreviewErrorCode.OUTPUT_INVALID
        if output_exists
        else PreviewErrorCode.OUTPUT_MISSING
    )
    return PreviewConversionError(
        code,
        stage="output_validation",
        source_path=file_path,
        converter="office",
        details=(
            f"Failed to convert {file_path.name} to a valid PDF for "
            "layout-preserving indexing. Install LibreOffice or set "
            "KH_OFFICE_TO_PDF_INDEXING=false to use direct Office text extraction."
        ),
    )
