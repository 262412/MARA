from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
from ktem_tests.preview_test_utils import SuccessfulSofficeRunner, write_ooxml


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))


@pytest.mark.parametrize(
    "module_name",
    [
        "ktem.pages.chat.page_preview_office",
        "ktem.docqa.preview_support",
    ],
)
def test_legacy_office_preview_imports_keep_public_methods(module_name):
    service_class = importlib.import_module(module_name).OfficePreviewConversionService

    assert callable(service_class.find_soffice_binary)
    for method_name in (
        "convert_to_pdf_preview",
        "get_cached_pdf_preview",
    ):
        assert callable(getattr(service_class, method_name))
    if module_name == "ktem.pages.chat.page_preview_office":
        assert callable(service_class.get_status)
        assert callable(service_class.schedule_conversion)


def test_web_and_docqa_paths_reexport_one_compatibility_service():
    from ktem.docqa.preview_support import (
        OfficePreviewConversionService as DocQAOfficePreviewConversionService,
    )
    from ktem.pages.chat.page_preview_office import (
        OfficePreviewConversionService as WebOfficePreviewConversionService,
    )

    assert WebOfficePreviewConversionService is DocQAOfficePreviewConversionService


@pytest.mark.parametrize(
    "module_name",
    [
        "ktem.pages.chat.page_preview_office",
        "ktem.docqa.preview_support",
    ],
)
def test_legacy_success_returns_string_in_existing_preview_cache(
    monkeypatch, tmp_path, module_name
):
    module = importlib.import_module(module_name)
    service_class = module.OfficePreviewConversionService
    source = write_ooxml(tmp_path / "source" / "layout.docx")
    runner = SuccessfulSofficeRunner()
    monkeypatch.setattr(
        service_class,
        "find_soffice_binary",
        staticmethod(lambda: "soffice"),
    )
    monkeypatch.setattr(subprocess, "run", runner)

    service = service_class()
    output = service.convert_to_pdf_preview(str(source), source.name)

    output_path = Path(output)
    assert isinstance(output, str)
    assert output_path.is_file()
    assert output_path.parent == tmp_path / "gradio" / "pdf_previews"
    assert service.get_cached_pdf_preview(str(source)) == output


@pytest.mark.parametrize(
    "module_name",
    [
        "ktem.pages.chat.page_preview_office",
        "ktem.docqa.preview_support",
    ],
)
def test_legacy_converter_failure_retains_empty_string_fallback(
    monkeypatch, tmp_path, module_name
):
    module = importlib.import_module(module_name)
    service_class = module.OfficePreviewConversionService
    source = write_ooxml(tmp_path / "slides.pptx")
    monkeypatch.setattr(
        service_class,
        "find_soffice_binary",
        staticmethod(lambda: ""),
    )

    service = service_class()

    assert service.convert_to_pdf_preview(str(source), source.name) == ""
    assert service.get_cached_pdf_preview(str(source)) == ""


def test_supported_office_extensions_remain_unchanged():
    from ktem.docqa.preview_support import OFFICE_EXTENSIONS as docqa_extensions
    from ktem.pages.chat.page_preview_handlers import (
        DocumentOfficePreviewHandler,
        PresentationOfficePreviewHandler,
        SpreadsheetOfficePreviewHandler,
    )
    from ktem.pages.chat.page_preview_types import OFFICE_EXTENSIONS as web_extensions

    expected = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    assert web_extensions == expected
    assert docqa_extensions == expected
    assert set(DocumentOfficePreviewHandler.supported_extensions) == {".doc", ".docx"}
    assert set(PresentationOfficePreviewHandler.supported_extensions) == {
        ".ppt",
        ".pptx",
    }
    assert set(SpreadsheetOfficePreviewHandler.supported_extensions) == {
        ".xls",
        ".xlsx",
    }


class _NoticeController:
    def __init__(self, status: str):
        self._status = status
        self._office_placeholder_shown = {"file-1"}
        self._non_pdf_preview_cache = {"file-1": ["fallback-page"]}
        self._total_pages_cache: dict[str, int] = {}

    def _get_cached_office_pdf_preview(self, _path):
        return ""

    def _schedule_office_pdf_conversion(self, _path, _name):
        return None

    def _get_non_pdf_preview_src(self, *_args):
        return "fallback-page"

    def _get_office_job_status(self, _path):
        return self._status

    @staticmethod
    def _clamp_page(page, total):
        return min(max(1, page), total)

    @staticmethod
    def _notice_html(message):
        return f"<div class='pdf-preview-notice'>{message}</div>"


@pytest.mark.parametrize(
    ("status", "expected_notice"),
    [
        ("queued", "Generating PDF preview in background..."),
        ("failed", "PDF conversion failed. Showing text preview."),
    ],
)
def test_office_placeholder_notices_remain_exact(status, expected_notice):
    from ktem.pages.chat.page_preview_handlers import DocumentOfficePreviewHandler
    from ktem.pages.chat.page_preview_models import PreviewPayloadContext

    context = PreviewPayloadContext(
        file_id="file-1",
        effective_name="report.docx",
        effective_path="/tmp/report.docx",
        source_extension=".docx",
        page=1,
        cached_total=1,
    )

    payload = DocumentOfficePreviewHandler(_NoticeController(status)).build(context)

    assert payload.preview_src == "fallback-page"
    assert payload.preview_notice == (
        f"<div class='pdf-preview-notice'>{expected_notice}</div>"
    )
