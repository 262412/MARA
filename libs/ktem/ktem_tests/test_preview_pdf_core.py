from __future__ import annotations

import importlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pypdf
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


def test_page_uses_one_stable_snapshot_when_path_is_replaced(monkeypatch, tmp_path):
    import ktem.preview.pdf as pdf_module
    from ktem.preview.pdf import PdfService

    source = write_text_pdf(tmp_path / "report.pdf", ["Old page one", "Old page two"])
    replacement = write_text_pdf(tmp_path / "replacement.pdf", ["New page one"])
    real_reader = pypdf.PdfReader
    reader_calls = 0

    def replacing_reader(*args, **kwargs):
        nonlocal reader_calls
        reader_calls += 1
        if reader_calls == 2:
            os.replace(replacement, source)
        return real_reader(*args, **kwargs)

    monkeypatch.setattr(pypdf, "PdfReader", replacing_reader)
    monkeypatch.setattr(pdf_module, "PdfReader", replacing_reader, raising=False)

    page = PdfService().page(source, 2)

    assert reader_calls == 1
    assert page.page == 2
    assert page.total_pages == 2
    assert page.text == "Old page two"


def test_parallel_same_page_miss_parses_one_snapshot(monkeypatch, tmp_path):
    import ktem.preview.pdf as pdf_module
    from ktem.preview.pdf import PdfService

    source = write_text_pdf(tmp_path / "report.pdf", ["Shared page"])
    real_reader = pypdf.PdfReader
    reader_calls = 0
    calls_lock = threading.Lock()

    def counting_reader(*args, **kwargs):
        nonlocal reader_calls
        with calls_lock:
            reader_calls += 1
        time.sleep(0.02)
        return real_reader(*args, **kwargs)

    monkeypatch.setattr(pypdf, "PdfReader", counting_reader)
    monkeypatch.setattr(pdf_module, "PdfReader", counting_reader, raising=False)
    service = PdfService()

    with ThreadPoolExecutor(max_workers=8) as executor:
        pages = list(executor.map(lambda _index: service.page(source, 1), range(8)))

    assert [page.text for page in pages] == ["Shared page"] * 8
    assert reader_calls == 1


def test_pdf_count_text_and_path_caches_are_bounded_lru(tmp_path):
    import ktem.preview.pdf as pdf_module

    sources = [
        write_text_pdf(tmp_path / f"report-{index}.pdf", [f"Document {index}"])
        for index in range(3)
    ]
    service = getattr(pdf_module, "PdfService")(max_cache_entries=2)

    for source in sources:
        service.page(source, 1, max_chars=4)

    assert len(service._count_cache) == 2
    assert len(service._path_signatures) == 2
    assert len(service._text_cache) == 2
    assert all(key[2] == 4 for key in service._text_cache)

    service.page(sources[-1], 1, max_chars=5)
    service.page(sources[-1], 1, max_chars=6)

    assert len(service._text_cache) == 2
    assert {key[2] for key in service._text_cache} == {5, 6}
