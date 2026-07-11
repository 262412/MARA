import subprocess
from pathlib import Path

from ktem.utils.office_conversion import (
    LAYOUT_PRESERVING_OFFICE_EXTENSIONS,
    OFFICE_EXTENSIONS,
    OfficeToPdfConversionService,
    detect_office_extension,
    get_file_signature,
    get_office_pdf_cache_dir,
    is_valid_pdf,
)
from ktem_tests.preview_test_utils import (
    SuccessfulSofficeRunner,
    write_ooxml,
    write_valid_pdf,
)


def test_detect_office_extension_recognizes_docx_package(tmp_path):
    docx_path = tmp_path / "upload"
    import zipfile

    with zipfile.ZipFile(docx_path, "w") as zf:
        zf.writestr("word/document.xml", "<w:document />")

    assert detect_office_extension("", str(docx_path)) == ".docx"


def test_legacy_office_conversion_imports_and_cache_helpers_remain_compatible(
    monkeypatch, tmp_path
):
    source = write_ooxml(tmp_path / "source.docx")
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(
        "ktem.utils.office_conversion.flowsettings.KH_OFFICE_PDF_CACHE_DIR",
        cache_dir,
        raising=False,
    )

    assert OFFICE_EXTENSIONS == {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    assert LAYOUT_PRESERVING_OFFICE_EXTENSIONS == {".doc", ".docx"}
    assert len(get_file_signature(source)) == 32
    assert get_office_pdf_cache_dir() == cache_dir
    assert is_valid_pdf(write_valid_pdf(tmp_path / "fixture.pdf"))


def test_office_to_pdf_converter_uses_isolated_libreoffice_output(
    monkeypatch, tmp_path
):
    from ktem.preview.office import OfficeConversionService

    source_path = write_ooxml(tmp_path / "layout.docx")
    runner = SuccessfulSofficeRunner()

    monkeypatch.setattr(
        "ktem.utils.office_conversion.find_soffice_binary",
        lambda: "soffice",
    )
    monkeypatch.setattr("ktem.preview.office.find_soffice_binary", lambda: "soffice")
    monkeypatch.setattr(subprocess, "run", runner)

    converter = OfficeToPdfConversionService(cache_dir=tmp_path / "cache")
    output = converter.convert_to_pdf(source_path, source_path.name)

    output_path = Path(output)
    assert output_path.suffix == ".pdf"
    assert output_path.parent == tmp_path / "cache"
    assert output_path.is_file()
    assert isinstance(getattr(converter, "_core"), OfficeConversionService)
    assert runner.calls == 1
