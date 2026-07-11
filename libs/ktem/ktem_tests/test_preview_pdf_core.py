from __future__ import annotations

import importlib

import pytest
from ktem_tests.preview_test_utils import write_text_pdf


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))


def test_pdf_service_returns_canonical_count_clamped_text_and_cache_dimensions(
    tmp_path,
):
    from ktem.preview.pdf import PdfService

    source = write_text_pdf(
        tmp_path / "report.pdf",
        ["First   page\ntext", "Second page text"],
    )
    service = PdfService()

    low = service.page(source, 0, max_chars=7)
    high = service.page(source, 99, max_chars=100)
    full = service.page(source, 1, max_chars=100)

    assert service.page_count(source) == 2
    assert (low.page, low.total_pages, low.text) == (1, 2, "First p")
    assert (high.page, high.total_pages, high.text) == (2, 2, "Second page text")
    assert full.text == "First page text"
    assert low.path == source.resolve()
    assert low.signature == full.signature


def test_pdf_mutation_invalidates_count_and_page_text_cache(tmp_path):
    from ktem.preview.pdf import PdfService

    source = write_text_pdf(tmp_path / "changing.pdf", ["Version one", "Page two"])
    service = PdfService()
    first = service.page(source, 2)

    write_text_pdf(source, ["Replacement version with a different size"])
    second = service.page(source, 2)

    assert first.total_pages == 2
    assert first.text == "Page two"
    assert second.signature != first.signature
    assert second.total_pages == 1
    assert second.page == 1
    assert second.text == "Replacement version with a different size"


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_missing_and_corrupt_pdf_raise_typed_errors_not_fake_counts(tmp_path, kind):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError
    from ktem.preview.pdf import PdfService

    source = tmp_path / f"{kind}.pdf"
    if kind == "corrupt":
        source.write_bytes(b"%PDF-1.7\nnot a real PDF")

    with pytest.raises(PreviewSourceError) as caught:
        PdfService().page_count(source)

    expected = (
        PreviewErrorCode.SOURCE_MISSING
        if kind == "missing"
        else PreviewErrorCode.SOURCE_INVALID
    )
    assert caught.value.code is expected
    assert caught.value.stage == "pdf_validation"
    assert caught.value.source_path == source.resolve()
    assert caught.value.converter == "pypdf"


def test_pdf_service_types_are_exported_from_preview_package():
    preview = importlib.import_module("ktem.preview")
    PageContext = getattr(preview, "PageContext")
    PdfPage = getattr(preview, "PdfPage")
    PdfService = getattr(preview, "PdfService")
    PreviewPurpose = getattr(preview, "PreviewPurpose")

    assert PdfService.__module__ == "ktem.preview.pdf"
    assert PdfPage.__module__ == "ktem.preview.pdf"
    assert PreviewPurpose.__module__ == "ktem.preview.context"
    assert PageContext.__module__ == "ktem.preview.context"
