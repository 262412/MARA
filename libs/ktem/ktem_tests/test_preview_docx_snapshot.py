from __future__ import annotations

import logging
import zipfile

import pytest

from .docx_preview_test_utils import (
    add_high_ratio_archive_member,
    set_archive_member_compression_method,
    write_document,
)


@pytest.mark.parametrize(
    "strict_name", ["extract_docx_text_strict", "extract_docx_html_strict"]
)
def test_validation_and_parse_use_the_same_archive_snapshot(
    monkeypatch, tmp_path, strict_name
):
    import ktem.preview.docx as docx_preview

    source = write_document(
        tmp_path / "source.docx",
        lambda document: document.add_paragraph("Trusted snapshot"),
    )
    replacement = write_document(
        tmp_path / "replacement.docx",
        lambda document: document.add_paragraph("Unvalidated replacement"),
    )
    original_testzip = zipfile.ZipFile.testzip
    swapped = False

    def swap_after_validation(archive):
        nonlocal swapped
        result = original_testzip(archive)
        if not swapped:
            replacement.replace(source)
            swapped = True
        return result

    monkeypatch.setattr(zipfile.ZipFile, "testzip", swap_after_validation)
    strict_extract = getattr(docx_preview, strict_name)

    rendered = strict_extract(str(source))

    assert swapped
    assert "Trusted snapshot" in rendered
    assert "Unvalidated replacement" not in rendered


def test_archive_resource_limit_error_has_structured_reason(tmp_path):
    from ktem.preview.docx import extract_docx_text_strict
    from ktem.preview.errors import PreviewSourceError

    source = write_document(
        tmp_path / "resource-limit.docx",
        lambda document: document.add_paragraph("bounded"),
    )
    add_high_ratio_archive_member(source, "word/review-bomb.bin")

    with pytest.raises(PreviewSourceError) as caught:
        extract_docx_text_strict(str(source))

    assert caught.value.stage == "archive_validation"
    assert caught.value.reason == "archive_resource_limit"


def test_unknown_compression_has_structured_archive_reason(tmp_path):
    from ktem.preview.docx import extract_docx_html_strict
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    source = write_document(
        tmp_path / "method-99.docx",
        lambda document: document.add_paragraph("bounded"),
    )
    set_archive_member_compression_method(source, "word/document.xml", 99)

    with pytest.raises(PreviewSourceError) as caught:
        extract_docx_html_strict(str(source))

    assert caught.value.code is PreviewErrorCode.SOURCE_ARCHIVE_INVALID
    assert caught.value.stage == "docx_package"
    assert caught.value.source_path == source.resolve()
    assert caught.value.reason == "archive_unsupported_compression"


def test_unknown_compression_compatibility_is_empty_and_logs_reason(
    caplog,
    tmp_path,
):
    from ktem.preview.docx import extract_docx_html

    source = write_document(
        tmp_path / "method-99-compat.docx",
        lambda document: document.add_paragraph("bounded"),
    )
    set_archive_member_compression_method(source, "word/document.xml", 99)

    with caplog.at_level(logging.WARNING, logger="ktem.preview.docx"):
        rendered = extract_docx_html(str(source))

    assert rendered == ""
    assert "reason=archive_unsupported_compression" in caplog.text
