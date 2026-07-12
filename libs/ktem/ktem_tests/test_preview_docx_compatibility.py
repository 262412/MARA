from __future__ import annotations

import logging

import pytest

from .docx_preview_test_utils import invalidate_first_table_grid_span, write_document


@pytest.fixture(autouse=True)
def _temporary_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))


def test_web_and_docqa_docx_text_outputs_are_equivalent(tmp_path):
    def build(document):
        document.add_paragraph("Alpha beta")
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Gamma"
        table.cell(0, 1).text = "Delta"

    source = write_document(tmp_path / "text.docx", build)

    from ktem.docqa.preview_support import extract_docx_text as docqa_extract
    from ktem.pages.chat.page_preview_document import extract_docx_text as web_extract

    assert web_extract(str(source), max_chars=18) == "Alpha beta Gamma D"
    assert docqa_extract(str(source), max_chars=18) == web_extract(
        str(source), max_chars=18
    )


def test_web_and_docqa_functions_reexport_the_shared_docx_core():
    from ktem.docqa.preview_support import extract_docx_text as docqa_text
    from ktem.pages.chat.page_preview_document import extract_docx_html as web_html
    from ktem.pages.chat.page_preview_document import extract_docx_text as web_text
    from ktem.pages.chat.page_preview_document import paginate_docx_html as web_paginate
    from ktem.preview.docx import (
        extract_docx_html,
        extract_docx_text,
        paginate_docx_html,
    )

    assert web_html is extract_docx_html
    assert web_text is extract_docx_text
    assert web_paginate is paginate_docx_html
    assert docqa_text is extract_docx_text


def test_missing_and_corrupt_compatibility_fallbacks_remain_empty(tmp_path):
    from ktem.docqa.preview_support import extract_docx_text as docqa_text
    from ktem.pages.chat.page_preview_document import extract_docx_html as web_html
    from ktem.pages.chat.page_preview_document import extract_docx_text as web_text

    missing = tmp_path / "missing.docx"
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not-docx")

    assert web_html(str(missing)) == ""
    assert web_text(str(missing)) == ""
    assert docqa_text(str(missing)) == ""
    assert web_html(str(corrupt)) == ""
    assert web_text(str(corrupt)) == ""
    assert docqa_text(str(corrupt)) == ""


@pytest.mark.parametrize("compat_name", ["extract_docx_text", "extract_docx_html"])
@pytest.mark.parametrize("invalid_source", [None, "invalid\0source.docx"])
def test_invalid_docx_paths_keep_empty_actionable_compatibility_fallback(
    caplog, compat_name, invalid_source
):
    import ktem.preview.docx as docx_preview

    compat_extract = getattr(docx_preview, compat_name)

    with caplog.at_level(logging.WARNING):
        result = compat_extract(invalid_source)

    assert result == ""
    assert "code=source_invalid" in caplog.text
    assert "stage=docx_source" in caplog.text
    assert "converter=python-docx" in caplog.text
    assert repr(invalid_source) in caplog.text


def test_invalid_required_table_xml_keeps_empty_logged_compatibility_fallback(
    tmp_path, caplog
):
    from ktem.preview.docx import extract_docx_html

    source = write_document(
        tmp_path / "invalid-table.docx",
        lambda document: document.add_table(rows=1, cols=1),
    )
    invalidate_first_table_grid_span(source)

    with caplog.at_level(logging.WARNING):
        result = extract_docx_html(str(source))

    assert result == ""
    assert "code=source_invalid" in caplog.text
    assert "stage=docx_render" in caplog.text
    assert str(source.resolve()) in caplog.text
    assert "converter=python-docx" in caplog.text


def test_non_pdf_page_cache_and_page_clamp_behavior_are_preserved(monkeypatch):
    from ktem.pages.chat.page_preview_non_pdf import NonPdfPreviewService

    class Controller:
        _non_pdf_preview_cache = {}
        _total_pages_cache = {}

    service = NonPdfPreviewService(Controller())
    calls = {"chunks": 0, "rich": 0}

    def get_chunks(_file_id):
        calls["chunks"] += 1
        return ["fallback text"]

    def get_rich(_file_name, _file_path):
        calls["rich"] += 1
        return (
            "<div class='docx-preview'><p>One<span "
            "class='docx-page-break'></span></p><p>Two</p></div>"
        )

    monkeypatch.setattr(service, "_get_index_preview_chunks", get_chunks)
    monkeypatch.setattr(service, "_build_rich_html", get_rich)
    monkeypatch.setattr(
        "ktem.pages.chat.page_preview_non_pdf.build_html_pages",
        lambda pages: [f"encoded:{page}" for page in pages],
    )

    last_page = service.get_preview_src("doc-1", "report.docx", "unused", 99)
    first_page = service.get_preview_src("doc-1", "report.docx", "unused", 1)

    assert last_page.endswith("<div class='docx-preview'><p>Two</p></div>")
    assert first_page.endswith(
        "<div class='docx-preview'><p>One<span "
        "class='docx-page-break'></span></p></div>"
    )
    assert service._controller._total_pages_cache == {"doc-1": 2}
    assert calls == {"chunks": 1, "rich": 1}
