from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ktem.assets import ICONS_DIR
from ktem.pages.chat.page_preview_presentation import PresentationPreviewService
from ktem.pages.chat.page_preview_runtime import (
    ensure_pdf_preview_copy,
    notice_html,
)
from ktem.preview.allowed_paths import build_gradio_allowed_paths


def test_gradio_allowed_paths_are_exact_preview_and_ui_roots(tmp_path):
    pdfjs = tmp_path / "app" / "assets" / "pdfjs" / "6.1.200"
    gradio_temp = tmp_path / "gradio"
    docs = tmp_path / "docs"

    assert build_gradio_allowed_paths(
        pdfjs_dir=pdfjs,
        gradio_temp_dir=gradio_temp,
        doc_dir=docs,
    ) == [
        str(ICONS_DIR.resolve()),
        str(pdfjs.resolve()),
        str(docs.resolve()),
        str((gradio_temp / "pdf_previews").resolve()),
    ]
    assert (gradio_temp / "pdf_previews").is_dir()


def test_pdf_preview_copy_uses_source_signature_to_avoid_basename_collision(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))
    first = tmp_path / "first" / "report.pdf"
    second = tmp_path / "second" / "report.pdf"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"%PDF-1.4\nfirst" + b"0" * 64)
    second.write_bytes(b"%PDF-1.4\nsecond" + b"0" * 64)

    first_copy = Path(ensure_pdf_preview_copy(str(first), first.name))
    second_copy = Path(ensure_pdf_preview_copy(str(second), second.name))

    assert first_copy != second_copy
    assert first_copy.parent == second_copy.parent == tmp_path / "gradio/pdf_previews"
    assert first_copy.read_bytes() == first.read_bytes()
    assert second_copy.read_bytes() == second.read_bytes()


def test_preview_notice_escapes_attacker_controlled_diagnostic():
    payload = '<img src=x onerror="window.__maraNoticeXss=1">'

    rendered = notice_html(payload)

    assert payload not in rendered
    assert "&lt;img" in rendered
    assert "onerror=&quot;window.__maraNoticeXss=1&quot;" in rendered


def test_pptx_links_and_images_use_explicit_allowlists():
    service = PresentationPreviewService(SimpleNamespace())
    unsafe_run = SimpleNamespace(
        text="PPTX JS LINK",
        font=None,
        hyperlink=SimpleNamespace(address="javascript:window.__maraPptxXss=1"),
    )
    safe_run = SimpleNamespace(
        text="PPTX HTTP LINK",
        font=None,
        hyperlink=SimpleNamespace(address="https://example.test/safe"),
    )
    svg_shape = SimpleNamespace(
        image=SimpleNamespace(content_type="image/svg+xml", blob=b"<svg/>"),
    )

    unsafe_html = service._render_run(unsafe_run)
    safe_html = service._render_run(safe_run)
    image_html = service._render_picture_shape(svg_shape, 1, 1, 1)

    assert "PPTX JS LINK" in unsafe_html
    assert "href=" not in unsafe_html
    assert "href='https://example.test/safe'" in safe_html
    assert image_html == ""
