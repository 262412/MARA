from __future__ import annotations

from pathlib import Path

import pytest
from ktem_tests.preview_test_utils import write_valid_pdf


def test_acceptance_pdf_conversion_delegates_without_direct_subprocess(
    monkeypatch, tmp_path
):
    import ktem.docqa.acceptance as acceptance_module
    from ktem.docqa.acceptance import AcceptanceMatrix
    from ktem.preview.context import PreviewPurpose

    source = tmp_path / "sample.docx"
    source.write_bytes(b"source fixture")
    canonical = write_valid_pdf(tmp_path / "canonical" / "sample.pdf")
    output = tmp_path / "samples" / "matrix_report.pdf"
    calls = []

    class FakePreviewService:
        def prepare_pdf(self, file_path, file_name, *, purpose):
            calls.append((Path(file_path), file_name, purpose))
            return canonical

    monkeypatch.setattr(
        acceptance_module, "PreviewService", FakePreviewService, raising=False
    )
    monkeypatch.setattr(
        acceptance_module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("acceptance called subprocess directly"),
    )

    matrix = object.__new__(AcceptanceMatrix)
    matrix._convert_to_pdf(source, output)

    assert calls == [(source, source.name, PreviewPurpose.ACCEPTANCE)]
    assert output.is_file()
    assert output.read_bytes() == canonical.read_bytes()


def test_acceptance_translates_typed_conversion_error_with_diagnostics(
    monkeypatch, tmp_path
):
    import ktem.docqa.acceptance as acceptance_module
    from ktem.docqa.acceptance import AcceptanceFailure, AcceptanceMatrix
    from ktem.preview.errors import PreviewConversionError, PreviewErrorCode

    source = tmp_path / "sample.docx"

    class FailingPreviewService:
        def prepare_pdf(self, file_path, file_name, *, purpose):
            raise PreviewConversionError(
                PreviewErrorCode.CONVERTER_UNAVAILABLE,
                stage="converter_lookup",
                source_path=file_path,
                converter="libreoffice",
                details="Install LibreOffice.",
            )

    monkeypatch.setattr(
        acceptance_module, "PreviewService", FailingPreviewService, raising=False
    )
    matrix = object.__new__(AcceptanceMatrix)

    with pytest.raises(AcceptanceFailure) as caught:
        matrix._convert_to_pdf(source, tmp_path / "sample.pdf")

    message = str(caught.value)
    assert "converter_unavailable" in message
    assert "converter_lookup" in message
    assert "libreoffice" in message
    assert "Install LibreOffice" in message
