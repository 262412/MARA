from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from ktem_tests.preview_test_utils import (
    write_minimal_cfb,
    write_ooxml,
    write_valid_pdf,
)


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))


def _classify(path: Path, file_name: str | None = None, **kwargs):
    from ktem.preview.source import classify_preview_source

    return classify_preview_source(path, file_name=file_name, **kwargs)


def test_classifies_valid_pdf_by_signature(tmp_path):
    from ktem.preview.models import PreviewSourceKind

    source = write_valid_pdf(tmp_path / "report.pdf")

    classified = _classify(source)

    assert classified.kind is PreviewSourceKind.PDF
    assert classified.extension == ".pdf"
    assert classified.path == source.resolve()
    assert len(classified.signature) == 64


@pytest.mark.parametrize("extension", [".docx", ".pptx", ".xlsx"])
def test_classifies_valid_ooxml_by_package_marker(tmp_path, extension):
    from ktem.preview.models import PreviewSourceKind

    source = write_ooxml(tmp_path / f"upload{extension}")

    classified = _classify(source)

    assert classified.kind is PreviewSourceKind.OOXML
    assert classified.extension == extension


@pytest.mark.parametrize("extension", [".doc", ".ppt", ".xls"])
def test_classifies_legacy_cfb_using_declared_office_extension(tmp_path, extension):
    from ktem.preview.models import PreviewSourceKind

    source = write_minimal_cfb(tmp_path / f"legacy{extension}")

    classified = _classify(source)

    assert classified.kind is PreviewSourceKind.CFB
    assert classified.extension == extension


def test_corrupt_cfb_container_is_rejected_with_typed_context(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    corrupt = tmp_path / "corrupt.doc"
    corrupt.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"truncated")

    with pytest.raises(PreviewSourceError) as caught:
        _classify(corrupt)

    assert caught.value.code is PreviewErrorCode.SOURCE_INVALID
    assert caught.value.stage == "cfb_validation"
    assert "compound file" in caught.value.details.lower()


def test_missing_source_error_carries_actionable_context(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    missing = tmp_path / "missing.docx"

    with pytest.raises(PreviewSourceError) as caught:
        _classify(missing)

    assert caught.value.code is PreviewErrorCode.SOURCE_MISSING
    assert caught.value.stage == "source_classification"
    assert caught.value.source_path == missing.resolve()
    assert caught.value.converter == "source"
    assert "exists" in caught.value.details.lower()


def test_corrupt_pdf_is_rejected_with_typed_context(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nnot-a-real-pdf")

    with pytest.raises(PreviewSourceError) as caught:
        _classify(corrupt)

    assert caught.value.code is PreviewErrorCode.SOURCE_INVALID
    assert caught.value.source_path == corrupt.resolve()
    assert caught.value.stage == "pdf_validation"


def test_corrupt_ooxml_archive_is_rejected(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"PK\x03\x04truncated")

    with pytest.raises(PreviewSourceError) as caught:
        _classify(corrupt)

    assert caught.value.code is PreviewErrorCode.SOURCE_ARCHIVE_INVALID
    assert caught.value.stage == "archive_validation"
    assert "archive" in caught.value.details.lower()


@pytest.mark.parametrize(
    ("actual_extension", "declared_name"),
    [
        (".pdf", "renamed.docx"),
        (".docx", "renamed.pptx"),
        (".pptx", "renamed.xlsx"),
    ],
)
def test_signature_and_declared_type_mismatch_is_rejected(
    tmp_path, actual_extension, declared_name
):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    source = tmp_path / f"actual{actual_extension}"
    if actual_extension == ".pdf":
        write_valid_pdf(source)
    else:
        write_ooxml(source)

    with pytest.raises(PreviewSourceError) as caught:
        _classify(source, file_name=declared_name)

    assert caught.value.code is PreviewErrorCode.SOURCE_TYPE_MISMATCH
    assert caught.value.stage == "source_classification"
    assert actual_extension in caught.value.details
    assert Path(declared_name).suffix in caught.value.details


def test_modern_extension_on_cfb_source_is_rejected_as_mismatch(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError

    source = write_minimal_cfb(tmp_path / "renamed.docx")

    with pytest.raises(PreviewSourceError) as caught:
        _classify(source)

    assert caught.value.code is PreviewErrorCode.SOURCE_TYPE_MISMATCH
    assert ".docx" in caught.value.details


def test_ooxml_archive_entry_limit_is_enforced_before_conversion(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError
    from ktem.preview.models import ArchiveLimits

    source = tmp_path / "oversized.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/document.xml", "<document />")
        archive.writestr("extra/one.xml", "1")
        archive.writestr("extra/two.xml", "2")

    with pytest.raises(PreviewSourceError) as caught:
        _classify(source, archive_limits=ArchiveLimits(max_entries=2))

    assert caught.value.code is PreviewErrorCode.SOURCE_ARCHIVE_INVALID
    assert caught.value.stage == "archive_validation"
    assert "entry limit" in caught.value.details.lower()


def test_ooxml_uncompressed_size_limit_is_enforced(tmp_path):
    from ktem.preview.errors import PreviewErrorCode, PreviewSourceError
    from ktem.preview.models import ArchiveLimits

    source = tmp_path / "expanded.docx"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "x" * 2048)

    with pytest.raises(PreviewSourceError) as caught:
        _classify(
            source,
            archive_limits=ArchiveLimits(
                max_entries=10,
                max_uncompressed_bytes=1024,
                max_compression_ratio=10_000,
            ),
        )

    assert caught.value.code is PreviewErrorCode.SOURCE_ARCHIVE_INVALID
    assert "uncompressed size" in caught.value.details.lower()
