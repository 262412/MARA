from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from docx import Document as load_docx_document
from docx.document import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError

from .errors import PreviewErrorCode, PreviewSourceError
from .source import classify_preview_source

DOCX_CONVERTER = "python-docx"


class DocxPackageReader:
    def __init__(self, source_path: str | Path) -> None:
        self.source_path = Path(source_path).expanduser().resolve()

    def load_document(self) -> Document:
        self._require_source()
        self._validate_archive()
        try:
            return load_docx_document(str(self.source_path))
        except (
            PackageNotFoundError,
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
            KeyError,
            XMLSyntaxError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise docx_error(
                PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
                self.source_path,
                "docx_package",
                f"DOCX package is corrupt or malformed: {exc}",
            ) from exc

    def extract_text(self, max_chars: int = 9000) -> str:
        root = self._read_document_xml()
        texts: list[str] = []
        total_chars = 0
        for node in root.iter():
            if not node.tag.endswith("}t") or not node.text:
                continue
            texts.append(node.text)
            total_chars += len(node.text)
            if total_chars >= max_chars:
                break
        return " ".join(texts)[:max_chars]

    def _read_document_xml(self) -> ET.Element:
        self._require_source()
        self._validate_archive()
        try:
            with zipfile.ZipFile(self.source_path) as archive:
                payload = archive.read("word/document.xml")
        except (
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
            KeyError,
            NotImplementedError,
            OSError,
            RuntimeError,
        ) as exc:
            raise docx_error(
                PreviewErrorCode.SOURCE_ARCHIVE_INVALID,
                self.source_path,
                "docx_package",
                f"DOCX package is corrupt or missing word/document.xml: {exc}",
            ) from exc
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            raise docx_error(
                PreviewErrorCode.SOURCE_INVALID,
                self.source_path,
                "docx_text_xml",
                f"DOCX document XML is malformed: {exc}",
            ) from exc

    def _require_source(self) -> None:
        if self.source_path.is_file():
            return
        raise docx_error(
            PreviewErrorCode.SOURCE_MISSING,
            self.source_path,
            "docx_package",
            "DOCX source is missing or is not a regular file.",
        )

    def _validate_archive(self) -> None:
        try:
            source = classify_preview_source(
                self.source_path,
                file_name=self.source_path.name,
            )
        except PreviewSourceError as exc:
            stage = "archive_validation" if "exceeds" in exc.details else "docx_package"
            raise docx_error(
                exc.code,
                self.source_path,
                stage,
                f"DOCX package validation failed: {exc.details}",
            ) from exc
        if source.extension != ".docx":
            raise docx_error(
                PreviewErrorCode.SOURCE_TYPE_MISMATCH,
                self.source_path,
                "docx_package",
                f"Expected a DOCX package, detected {source.extension!r}.",
            )


def docx_error(
    code: PreviewErrorCode,
    source_path: str | Path,
    stage: str,
    details: str,
) -> PreviewSourceError:
    return PreviewSourceError(
        code,
        stage=stage,
        source_path=source_path,
        converter=DOCX_CONVERTER,
        details=details,
    )
