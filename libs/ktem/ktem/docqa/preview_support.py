from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader
from sqlmodel import Session, select

from ktem.db.models import engine
from ktem.utils.dependencies import find_soffice_binary

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
except Exception:
    Presentation = None
    MSO_SHAPE_TYPE = None


logger = logging.getLogger(__name__)

OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}


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


def read_text_file(file_path: str, max_chars: int = 9000) -> str:
    if not file_path or not os.path.isfile(file_path):
        return ""
    for enc in ("utf-8", "utf-16", "latin-1", "gbk"):
        try:
            with open(file_path, "r", encoding=enc, errors="ignore") as file_obj:
                content = file_obj.read(max_chars * 2)
            return content[:max_chars]
        except Exception:
            continue
    return ""


def extract_docx_text(file_path: str, max_chars: int = 9000) -> str:
    texts: list[str] = []
    try:
        with zipfile.ZipFile(file_path) as zf:
            with zf.open("word/document.xml") as file_obj:
                root = ET.fromstring(file_obj.read())
        total_chars = 0
        for node in root.iter():
            if node.tag.endswith("}t") and node.text:
                texts.append(node.text)
                total_chars += len(node.text)
                if total_chars >= max_chars:
                    break
    except Exception:
        return ""
    return " ".join(texts)[:max_chars]


def extract_xlsx_text(file_path: str, max_chars: int = 9000) -> str:
    try:
        with zipfile.ZipFile(file_path) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                with zf.open("xl/sharedStrings.xml") as file_obj:
                    ss_root = ET.fromstring(file_obj.read())
                for node in ss_root.iter():
                    if node.tag.endswith("}t") and node.text:
                        shared_strings.append(node.text)

            cells: list[str] = []
            total_chars = 0
            sheet_names = sorted(
                [
                    name
                    for name in zf.namelist()
                    if re.match(r"xl/worksheets/sheet\d+\.xml", name)
                ]
            )
            for sheet in sheet_names:
                with zf.open(sheet) as file_obj:
                    root = ET.fromstring(file_obj.read())
                for cell in root.iter():
                    if not cell.tag.endswith("}c"):
                        continue
                    cell_type = cell.attrib.get("t", "")
                    value = ""
                    for child in cell:
                        if child.tag.endswith("}v") and child.text:
                            value = child.text
                            break
                    if not value:
                        continue
                    if cell_type == "s":
                        try:
                            idx = int(value)
                            if 0 <= idx < len(shared_strings):
                                value = shared_strings[idx]
                        except Exception:
                            pass
                    cells.append(value)
                    total_chars += len(value)
                    if total_chars >= max_chars:
                        break
                if total_chars >= max_chars:
                    break
    except Exception:
        return ""
    return " ".join(cells)[:max_chars]


class PresentationTextService:
    def extract_slide_text(self, file_path: str, page: int, max_chars: int = 7000) -> str:
        if not file_path or not os.path.isfile(file_path) or Presentation is None:
            return ""

        try:
            presentation = Presentation(file_path)
        except Exception:
            return ""

        slides = list(presentation.slides)
        if not slides:
            return ""
        page_idx = max(0, min(len(slides) - 1, int(page or 1) - 1))
        texts: list[str] = []
        total_chars = 0
        for shape in slides[page_idx].shapes:
            self._collect_shape_text(shape, texts)
            total_chars = sum(len(item) for item in texts)
            if total_chars >= max_chars:
                break
        return " ".join(part for part in texts if part).strip()[:max_chars]

    def _collect_shape_text(self, shape, texts: list[str]) -> None:
        if getattr(shape, "has_text_frame", False):
            for paragraph in getattr(shape.text_frame, "paragraphs", []):
                paragraph_text = (getattr(paragraph, "text", "") or "").strip()
                if paragraph_text:
                    texts.append(" ".join(paragraph_text.split()))

        if getattr(shape, "has_table", False):
            try:
                for row in shape.table.rows:
                    for cell in row.cells:
                        cell_text = (getattr(cell, "text", "") or "").strip()
                        if cell_text:
                            texts.append(" ".join(cell_text.split()))
            except Exception:
                pass

        try:
            shape_type = getattr(shape, "shape_type", None)
            if MSO_SHAPE_TYPE is not None and shape_type == MSO_SHAPE_TYPE.GROUP:
                for item in getattr(shape, "shapes", []):
                    self._collect_shape_text(item, texts)
        except Exception:
            pass


class OfficePreviewConversionService:
    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)
        self._office_pdf_cache: dict[str, str] = {}

    @staticmethod
    def _get_file_signature(file_path: str) -> str:
        try:
            stat = os.stat(file_path)
            raw = f"{os.path.abspath(file_path)}|{stat.st_size}|{int(stat.st_mtime_ns)}"
        except Exception:
            raw = os.path.abspath(file_path)
        import hashlib

        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_valid_pdf(pdf_path: str) -> bool:
        try:
            if not pdf_path or (not os.path.isfile(pdf_path)):
                return False
            if os.path.getsize(pdf_path) < 64:
                return False
            pages = len(PdfReader(pdf_path, strict=False).pages)
            return pages > 0
        except Exception:
            return False

    @staticmethod
    def _get_pdf_preview_dir() -> str:
        import tempfile

        gradio_temp_dir = os.environ.get("GRADIO_TEMP_DIR", tempfile.gettempdir())
        preview_dir = os.path.join(gradio_temp_dir, "pdf_previews")
        os.makedirs(preview_dir, exist_ok=True)
        return preview_dir

    @staticmethod
    def find_soffice_binary() -> str:
        return find_soffice_binary()

    def convert_to_pdf_preview(self, file_path: str, file_name: str) -> str:
        if not file_path or not os.path.isfile(file_path):
            return ""
        ext = detect_office_extension(file_name, file_path)
        if ext not in {".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"}:
            return ""

        cache_key = self._get_file_signature(file_path)
        cached_output = self._office_pdf_cache.get(cache_key, "")
        if cached_output and os.path.isfile(cached_output):
            return cached_output

        preview_dir = self._get_pdf_preview_dir()
        stem = os.path.splitext(os.path.basename(file_path))[0]
        libreoffice_output_pdf = os.path.join(preview_dir, f"{stem}.pdf")
        output_pdf = os.path.join(preview_dir, f"{stem}_{cache_key[:12]}.pdf")

        convert_input_path = file_path
        temp_input_path = ""
        current_ext = os.path.splitext(file_path)[1].lower()
        if not current_ext and ext:
            temp_input_path = os.path.join(preview_dir, f"{stem}_{cache_key[:12]}{ext}")
            try:
                shutil.copyfile(file_path, temp_input_path)
                convert_input_path = temp_input_path
            except Exception:
                convert_input_path = file_path

        soffice_cmd = self.find_soffice_binary()
        if soffice_cmd:
            try:
                result = subprocess.run(
                    [
                        soffice_cmd,
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        preview_dir,
                        convert_input_path,
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120,
                )
                if os.path.isfile(libreoffice_output_pdf):
                    if libreoffice_output_pdf != output_pdf:
                        try:
                            shutil.copyfile(libreoffice_output_pdf, output_pdf)
                        except Exception:
                            output_pdf = libreoffice_output_pdf
                    self._office_pdf_cache[cache_key] = output_pdf
                    self._cleanup_temp_input(temp_input_path)
                    return output_pdf
                if os.path.isfile(output_pdf):
                    self._office_pdf_cache[cache_key] = output_pdf
                    self._cleanup_temp_input(temp_input_path)
                    return output_pdf
                stderr_msg = (result.stderr or "").strip()
                stdout_msg = (result.stdout or "").strip()
                if stderr_msg or stdout_msg:
                    self._logger.warning(
                        "LibreOffice conversion finished without output file. stdout=%s stderr=%s",
                        stdout_msg[:500],
                        stderr_msg[:500],
                    )
            except Exception as exc:
                self._logger.warning(
                    "Failed to convert office file to PDF preview via soffice: %s",
                    repr(exc),
                )
        else:
            self._logger.info("LibreOffice soffice binary not found. Skipping soffice conversion.")

        if ext in {".docx", ".doc"}:
            try:
                from docx2pdf import convert as docx2pdf_convert

                docx2pdf_convert(convert_input_path, output_pdf)
                if os.path.isfile(output_pdf):
                    self._office_pdf_cache[cache_key] = output_pdf
                    self._cleanup_temp_input(temp_input_path)
                    return output_pdf
            except Exception as exc:
                self._logger.warning(
                    "Failed to convert office file to PDF preview via docx2pdf: %s",
                    repr(exc),
                )

        self._cleanup_temp_input(temp_input_path)
        return ""

    def get_cached_pdf_preview(self, file_path: str) -> str:
        if not file_path or not os.path.isfile(file_path):
            return ""
        cache_key = self._get_file_signature(file_path)
        cached_pdf = self._office_pdf_cache.get(cache_key, "")
        if cached_pdf and os.path.isfile(cached_pdf) and self._is_valid_pdf(cached_pdf):
            return cached_pdf

        preview_dir = self._get_pdf_preview_dir()
        stem = os.path.splitext(os.path.basename(file_path))[0]
        recovered_pdf = os.path.join(preview_dir, f"{stem}_{cache_key[:12]}.pdf")
        if os.path.isfile(recovered_pdf) and self._is_valid_pdf(recovered_pdf):
            self._office_pdf_cache[cache_key] = recovered_pdf
            return recovered_pdf

        try:
            if os.path.isdir(preview_dir):
                for filename in os.listdir(preview_dir):
                    if filename.startswith(stem + "_") and filename.endswith(".pdf"):
                        candidate_path = os.path.join(preview_dir, filename)
                        if os.path.isfile(candidate_path) and self._is_valid_pdf(candidate_path):
                            self._office_pdf_cache[cache_key] = candidate_path
                            return candidate_path
        except Exception:
            pass

        return ""

    @staticmethod
    def _cleanup_temp_input(temp_input_path: str):
        if temp_input_path and os.path.isfile(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception:
                pass


class PreviewFileResolver:
    def __init__(self, app, file_name_cache: dict[str, str]):
        self._app = app
        self._file_name_cache = file_name_cache

    @staticmethod
    def extract_first_selected_file_id(selected_file_ids):
        if not selected_file_ids:
            return ""

        selected = selected_file_ids[0]
        if isinstance(selected, str) and selected.startswith("["):
            try:
                import json

                selected_items = json.loads(selected)
                return selected_items[0] if selected_items else ""
            except Exception:
                return ""

        return selected

    def resolve_file_path_by_id(self, file_id: str) -> str:
        if not file_id:
            return ""
        for index in self._app.index_manager.indices:
            resources = getattr(index, "_resources", {}) or {}
            source_table = resources.get("Source")
            file_storage_path = resources.get("FileStoragePath")
            if source_table is None:
                continue

            with Session(engine) as session:
                statement = select(source_table).where(source_table.id == file_id)
                source_obj = session.exec(statement).first()
            if not source_obj:
                continue

            self._file_name_cache[file_id] = getattr(source_obj, "name", "") or ""
            stored_path = getattr(source_obj, "path", "") or ""
            if not stored_path:
                continue

            if file_storage_path:
                candidate_storage_path = os.path.join(str(file_storage_path), stored_path)
                if os.path.isfile(candidate_storage_path):
                    return candidate_storage_path
            if os.path.isfile(stored_path):
                return stored_path
        return ""

    def resolve_file_name_by_id(self, file_id: str) -> str:
        if not file_id:
            return ""
        if file_id in self._file_name_cache:
            return self._file_name_cache[file_id]
        _ = self.resolve_file_path_by_id(file_id)
        return self._file_name_cache.get(file_id, "")

    def resolve_selected_file(self, selected_file_ids):
        file_id = self.extract_first_selected_file_id(selected_file_ids)
        if not file_id:
            return "", "", ""

        file_name = ""
        resolved_path = ""
        for index in self._app.index_manager.indices:
            resources = getattr(index, "_resources", {}) or {}
            source_table = resources.get("Source")
            file_storage_path = resources.get("FileStoragePath")
            if source_table is None:
                continue

            with Session(engine) as session:
                statement = select(source_table).where(source_table.id == file_id)
                source_obj = session.exec(statement).first()

            if not source_obj:
                continue

            file_name = getattr(source_obj, "name", "") or ""
            stored_path = getattr(source_obj, "path", "") or ""

            if stored_path and file_storage_path:
                candidate_storage_path = os.path.join(str(file_storage_path), stored_path)
                if os.path.isfile(candidate_storage_path):
                    resolved_path = candidate_storage_path
                    break

            if stored_path and os.path.isfile(stored_path):
                resolved_path = stored_path
                break

        if not file_name:
            file_name = self.resolve_file_name_by_id(file_id)
        if not resolved_path:
            resolved_path = self.resolve_file_path_by_id(file_id)

        return file_id, file_name, resolved_path


class PreviewSupportService:
    def __init__(self, app):
        self._app = app
        self._file_name_cache: dict[str, str] = {}
        self._resolver = PreviewFileResolver(app, self._file_name_cache)
        self._office_conversion = OfficePreviewConversionService(logger)
        self._presentation_service = PresentationTextService()

    def resolve_selected_file(
        self, selected_file_ids: list[str] | None
    ) -> tuple[str, str, str]:
        return self._resolver.resolve_selected_file(selected_file_ids or [])

    def resolve_file_path(self, file_id: str) -> str:
        return self._resolver.resolve_file_path_by_id(file_id)

    def resolve_file_name(self, file_id: str) -> str:
        return self._resolver.resolve_file_name_by_id(file_id)

    @staticmethod
    def extract_pdf_page_text(pdf_path: str, page_number: int, max_chars: int = 7000) -> str:
        if not pdf_path or not os.path.isfile(pdf_path):
            return ""
        try:
            reader = PdfReader(pdf_path)
            if not reader.pages:
                return ""
            page_idx = max(0, min(len(reader.pages) - 1, int(page_number or 1) - 1))
            text = reader.pages[page_idx].extract_text() or ""
            text = " ".join(str(text).split())
            return text[:max_chars]
        except Exception:
            return ""

    def get_page_context_text(
        self,
        file_id: str,
        file_name: str,
        page_number: int,
        max_chars: int = 7000,
    ) -> str:
        if not file_id or not file_name:
            return ""

        source_path = self.resolve_file_path(file_id)
        if not source_path:
            return ""

        source_extension = detect_office_extension(file_name, source_path)
        file_extension = (Path(file_name).suffix or Path(source_path).suffix).lower()

        if file_extension == ".pdf":
            return self.extract_pdf_page_text(source_path, page_number, max_chars=max_chars)

        if source_extension in {".pptx", ".ppt"}:
            return self._presentation_service.extract_slide_text(
                source_path,
                page_number,
                max_chars=max_chars,
            )

        if source_extension in {".docx", ".doc", ".xlsx", ".xls"}:
            cached_pdf = self._office_conversion.get_cached_pdf_preview(source_path)
            if not cached_pdf:
                cached_pdf = self._office_conversion.convert_to_pdf_preview(source_path, file_name)
            if cached_pdf and os.path.isfile(cached_pdf):
                return self.extract_pdf_page_text(cached_pdf, page_number, max_chars=max_chars)

        if file_extension in {".docx", ".doc"}:
            return extract_docx_text(source_path, max_chars=max_chars)
        if file_extension in {".xlsx", ".xls", ".csv"}:
            return extract_xlsx_text(source_path, max_chars=max_chars)
        if file_extension in {".txt", ".md", ".html", ".mhtml"}:
            return read_text_file(source_path, max_chars=max_chars)

        return ""
