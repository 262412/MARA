from types import SimpleNamespace

from ktem.index.file.pipelines import IndexDocumentPipeline
from ktem.preview.errors import PreviewConversionError, PreviewErrorCode


def _conversion_failure(file_path, _file_name):
    raise PreviewConversionError(
        PreviewErrorCode.CONVERTER_UNAVAILABLE,
        stage="converter_lookup",
        source_path=file_path,
        converter="libreoffice",
        details="Install LibreOffice.",
    )


def test_layout_preserving_docx_conversion_falls_back_only_when_non_strict(
    monkeypatch, tmp_path
):
    source_path = tmp_path / "layout.docx"
    source_path.write_bytes(b"docx")
    monkeypatch.setattr(
        "ktem.index.file.pipelines.get_office_pdf_converter",
        lambda: SimpleNamespace(convert_to_pdf=_conversion_failure),
    )
    monkeypatch.setattr(
        "ktem.index.file.pipelines.settings.KH_OFFICE_TO_PDF_INDEXING_STRICT",
        False,
        raising=False,
    )

    pipeline = IndexDocumentPipeline(embedding=SimpleNamespace())
    parse_path, metadata = pipeline.prepare_layout_preserving_parse_file(source_path)

    assert parse_path == source_path
    assert metadata is not None
    assert metadata["source_file_name"] == "layout.docx"
    assert metadata["source_file_extension"] == ".docx"
    assert metadata["converted_from_office"] is False
    assert metadata["layout_preserving_parse"] is False
    assert metadata["direct_office_text_fallback"] is True
    assert "converter_unavailable" in metadata["office_pdf_conversion_error"]
    assert "Install LibreOffice" in metadata["office_pdf_conversion_error"]
