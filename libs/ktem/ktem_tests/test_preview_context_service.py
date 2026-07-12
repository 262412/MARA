from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
from ktem_tests.preview_test_utils import (
    SuccessfulSofficeRunner,
    write_ooxml,
    write_text_pdf,
)


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv(
        "KH_OFFICE_PDF_CACHE_DIR", str(tmp_path / "app-data" / "office-cache")
    )
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))


def test_preview_service_builds_equal_web_and_docqa_pdf_context(tmp_path):
    from ktem.preview.context import PreviewPurpose
    from ktem.preview.service import PreviewService

    source = write_text_pdf(tmp_path / "report.pdf", ["Shared   page\ncontext"])
    web = PreviewService().page_context(
        source, source.name, 1, purpose=PreviewPurpose.WEB
    )
    docqa = PreviewService().page_context(
        source, source.name, 1, purpose=PreviewPurpose.DOCQA
    )

    assert web.page == docqa.page == 1
    assert web.total_pages == docqa.total_pages == 1
    assert web.text == docqa.text == "Shared page context"
    assert web.pdf_path == docqa.pdf_path == source.resolve()


def test_docqa_empty_page_context_is_typed_while_web_can_retain_fallback(tmp_path):
    from ktem.preview.context import PreviewPurpose
    from ktem.preview.service import PreviewService

    errors = importlib.import_module("ktem.preview.errors")
    PreviewContextError = getattr(errors, "PreviewContextError")
    context_unavailable = getattr(errors.PreviewErrorCode, "CONTEXT_TEXT_UNAVAILABLE")

    source = write_text_pdf(tmp_path / "scan.pdf", [""])
    service = PreviewService()

    web = service.page_context(
        source,
        source.name,
        1,
        purpose=PreviewPurpose.WEB,
        fallback_text="OCR   fallback",
    )
    assert web.text == "OCR fallback"
    assert web.used_text_fallback is True

    with pytest.raises(PreviewContextError) as caught:
        service.page_context(
            source,
            source.name,
            1,
            purpose=PreviewPurpose.DOCQA,
        )
    assert caught.value.code is context_unavailable
    assert caught.value.stage == "page_context"


def test_all_conversion_consumers_share_one_canonical_office_artifact(
    monkeypatch, tmp_path
):
    from ktem.docqa.preview_support import (
        OfficePreviewConversionService as DocQAOfficePreviewConversionService,
    )
    from ktem.pages.chat.page_preview_office import (
        OfficePreviewConversionService as WebOfficePreviewConversionService,
    )
    from ktem.preview.context import PreviewPurpose
    from ktem.preview.service import PreviewService, canonical_office_cache_dir
    from ktem.utils.office_conversion import OfficeToPdfConversionService

    source = write_ooxml(tmp_path / "source" / "shared.docx")
    runner = SuccessfulSofficeRunner()
    monkeypatch.setattr(
        WebOfficePreviewConversionService,
        "find_soffice_binary",
        staticmethod(lambda: "soffice"),
    )
    monkeypatch.setattr("ktem.preview.office.find_soffice_binary", lambda: "soffice")
    monkeypatch.setattr(subprocess, "run", runner)

    web_output = WebOfficePreviewConversionService().convert_to_pdf_preview(
        str(source), source.name
    )
    docqa_output = DocQAOfficePreviewConversionService().convert_to_pdf_preview(
        str(source), source.name
    )
    indexing_output = OfficeToPdfConversionService().convert_to_pdf(source, source.name)
    acceptance_output = PreviewService().prepare_pdf(
        source, source.name, purpose=PreviewPurpose.ACCEPTANCE
    )

    canonical_dir = canonical_office_cache_dir()
    assert runner.calls == 1
    assert Path(indexing_output).parent == canonical_dir
    assert acceptance_output == Path(indexing_output)
    assert Path(web_output) == Path(docqa_output)
    assert Path(web_output).parent == tmp_path / "gradio" / "pdf_previews"
    assert Path(web_output).name == Path(indexing_output).name
    assert Path(web_output).read_bytes() == Path(indexing_output).read_bytes()


def test_office_page_context_keeps_original_source_and_pdf_artifact_paths(tmp_path):
    from ktem.preview.context import PreviewPurpose
    from ktem.preview.service import PreviewService

    source = write_ooxml(tmp_path / "source" / "report.docx")
    artifact = write_text_pdf(tmp_path / "canonical" / "report.pdf", ["Page text"])

    class FakeOfficeConverter:
        cache_dir = artifact.parent

        def convert_to_pdf(self, _file_path, _file_name=None):
            return artifact

        def get_cached_pdf(self, _file_path, _file_name=None):
            return artifact

    context = PreviewService(office=FakeOfficeConverter()).page_context(
        source,
        source.name,
        1,
        purpose=PreviewPurpose.DOCQA,
    )

    assert context.source_path == source.resolve()
    assert context.pdf_path == artifact.resolve()
