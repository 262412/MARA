from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from theflow.settings import settings as flowsettings

from .dependencies import find_soffice_binary

logger = logging.getLogger(__name__)

OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}
LAYOUT_PRESERVING_OFFICE_EXTENSIONS = {".docx", ".doc"}


def detect_office_extension(file_name: str, file_path: str) -> str:
    ext = os.path.splitext((file_name or file_path or ""))[1].lower()
    if ext in OFFICE_EXTENSIONS:
        return ext

    if file_path and os.path.isfile(file_path):
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path) as zf:
                    names = set(zf.namelist())
                if "word/document.xml" in names:
                    return ".docx"
                if "ppt/presentation.xml" in names:
                    return ".pptx"
                if "xl/workbook.xml" in names:
                    return ".xlsx"
        except Exception:
            pass

        try:
            with open(file_path, "rb") as file_obj:
                header = file_obj.read(8)
            if header.startswith(b"\xD0\xCF\x11\xE0"):
                return ".doc"
        except Exception:
            pass

    return ""


def get_file_signature(file_path: str | Path) -> str:
    try:
        path = Path(file_path)
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime_ns)}"
    except Exception:
        raw = os.path.abspath(os.fspath(file_path))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def is_valid_pdf(pdf_path: str | Path) -> bool:
    try:
        path = Path(pdf_path)
        if not path.is_file() or path.stat().st_size < 64:
            return False
        from pypdf import PdfReader

        return len(PdfReader(str(path), strict=False).pages) > 0
    except Exception:
        return False


def get_office_pdf_cache_dir() -> Path:
    configured = getattr(flowsettings, "KH_OFFICE_PDF_CACHE_DIR", None)
    if configured:
        return _ensure_dir(Path(configured))

    app_data_dir = getattr(flowsettings, "KH_APP_DATA_DIR", None)
    if app_data_dir:
        return _ensure_dir(Path(app_data_dir) / "office_pdf_cache_dir")

    return _ensure_dir(Path(tempfile.gettempdir()) / "kotaemon_office_pdf_cache")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class OfficeToPdfConversionService:
    """Convert Office documents to PDF for layout-preserving downstream parsing."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        logger: logging.Logger | None = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else get_office_pdf_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger or logging.getLogger(__name__)
        self._cache: dict[str, str] = {}

    def convert_to_pdf(
        self, file_path: str | Path, file_name: str | None = None
    ) -> str:
        source_path = Path(file_path)
        if not source_path.is_file():
            return ""

        ext = detect_office_extension(file_name or source_path.name, str(source_path))
        if ext not in OFFICE_EXTENSIONS:
            return ""

        cache_key = get_file_signature(source_path)
        cached_output = self._cache.get(cache_key, "")
        if cached_output and is_valid_pdf(cached_output):
            return cached_output

        output_pdf = self.cache_dir / f"{source_path.stem}_{cache_key[:12]}.pdf"
        if is_valid_pdf(output_pdf):
            self._cache[cache_key] = str(output_pdf)
            return str(output_pdf)

        job_dir = self.cache_dir / cache_key[:12]
        job_dir.mkdir(parents=True, exist_ok=True)
        convert_input_path = job_dir / f"{source_path.stem}{ext}"
        try:
            shutil.copyfile(source_path, convert_input_path)
        except Exception:
            convert_input_path = source_path

        try:
            converted = self._convert_with_soffice(convert_input_path, job_dir)
            if converted and is_valid_pdf(converted):
                shutil.copyfile(converted, output_pdf)
                self._cache[cache_key] = str(output_pdf)
                return str(output_pdf)

            if ext in {".docx", ".doc"}:
                converted = self._convert_with_docx2pdf(convert_input_path, output_pdf)
                if converted and is_valid_pdf(converted):
                    self._cache[cache_key] = str(output_pdf)
                    return str(output_pdf)
        finally:
            if convert_input_path != source_path:
                self._cleanup_path(job_dir)

        return ""

    def _convert_with_soffice(self, input_path: Path, output_dir: Path) -> Path | None:
        soffice_cmd = find_soffice_binary()
        if not soffice_cmd:
            self._logger.info("LibreOffice soffice binary not found.")
            return None

        try:
            result = subprocess.run(
                [
                    soffice_cmd,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(input_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            self._logger.warning("Failed to convert Office file via soffice: %s", exc)
            return None

        expected_pdf = output_dir / f"{input_path.stem}.pdf"
        if expected_pdf.is_file():
            return expected_pdf

        stderr_msg = (result.stderr or "").strip()
        stdout_msg = (result.stdout or "").strip()
        if stderr_msg or stdout_msg:
            self._logger.warning(
                "LibreOffice conversion finished without output file. stdout=%s stderr=%s",
                stdout_msg[:500],
                stderr_msg[:500],
            )
        return None

    def _convert_with_docx2pdf(self, input_path: Path, output_pdf: Path) -> Path | None:
        try:
            from docx2pdf import convert as docx2pdf_convert

            docx2pdf_convert(str(input_path), str(output_pdf))
        except Exception as exc:
            self._logger.warning("Failed to convert Office file via docx2pdf: %s", exc)
            return None

        return output_pdf if output_pdf.is_file() else None

    @staticmethod
    def _cleanup_path(path: Path) -> None:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file():
                path.unlink()
        except Exception:
            pass
