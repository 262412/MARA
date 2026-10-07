"""A successful exit without a new PDF must never publish an old output."""

from types import SimpleNamespace

import pytest
from slide_cli import deck


@pytest.mark.parametrize("renamed", [False, True])
def test_old_pdf_cannot_be_mistaken_for_this_conversion(tmp_path, monkeypatch, renamed):
    source = tmp_path / "source.pptx"
    source.write_bytes(b"owned converter input")
    old = tmp_path / "source.pdf"
    old.write_bytes(b"previous independent export")
    requested = tmp_path / "requested.pdf" if renamed else old
    monkeypatch.setattr(
        deck.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )
    with pytest.raises(RuntimeError, match="expected PDF output"):
        deck.export_deck_pdf(source, output_path=requested, soffice_path="owned")
    assert old.read_bytes() == b"previous independent export"
    if renamed:
        assert not requested.exists()
