from pathlib import Path
from types import SimpleNamespace

from ktem.utils.office_conversion import (
    OfficeToPdfConversionService,
    detect_office_extension,
)


def test_detect_office_extension_recognizes_docx_package(tmp_path):
    docx_path = tmp_path / "upload"
    import zipfile

    with zipfile.ZipFile(docx_path, "w") as zf:
        zf.writestr("word/document.xml", "<w:document />")

    assert detect_office_extension("", str(docx_path)) == ".docx"


def test_office_to_pdf_converter_uses_isolated_libreoffice_output(
    monkeypatch, tmp_path
):
    source_path = tmp_path / "layout.docx"
    source_path.write_bytes(b"docx")

    def fake_run(command, **_kwargs):
        output_dir = command[command.index("--outdir") + 1]
        input_path = command[-1]
        output_path = Path(output_dir) / (Path(input_path).stem + ".pdf")
        output_path.write_bytes(b"%PDF-test")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "ktem.utils.office_conversion.find_soffice_binary",
        lambda: "soffice",
    )
    monkeypatch.setattr("ktem.utils.office_conversion.subprocess.run", fake_run)
    monkeypatch.setattr(
        "ktem.utils.office_conversion.is_valid_pdf",
        lambda path: Path(path).is_file() and str(path).endswith(".pdf"),
    )

    converter = OfficeToPdfConversionService(cache_dir=tmp_path / "cache")
    output = converter.convert_to_pdf(source_path, source_path.name)

    output_path = Path(output)
    assert output_path.suffix == ".pdf"
    assert output_path.parent == tmp_path / "cache"
    assert output_path.is_file()
