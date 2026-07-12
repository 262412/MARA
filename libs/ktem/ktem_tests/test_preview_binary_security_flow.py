from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

from ktem.assets.pdfjs_assets import materialize_pdfjs
from ktem.pages.chat.page_preview_document import extract_docx_html
from ktem.pages.chat.page_preview_presentation import PresentationPreviewService
from ktem.pages.chat.page_preview_runtime import (
    build_pdfjs_viewer_src,
    ensure_pdf_preview_copy,
    safe_pdf_page_count,
)
from theflow.settings import settings as flowsettings

REPO_ROOT = Path(__file__).resolve().parents[3]


def _fixture_factory():
    source = REPO_ROOT / "tests/browser/preview_fixture_factory.py"
    spec = importlib.util.spec_from_file_location("preview_fixture_factory", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_binary_fixtures_cross_production_preview_boundaries(
    monkeypatch,
    tmp_path,
):
    fixture_dir = tmp_path / "fixtures"
    _fixture_factory().build_fixtures(fixture_dir)
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setattr(
        flowsettings,
        "KH_APP_DATA_DIR",
        tmp_path / "app-data",
        raising=False,
    )
    materialize_pdfjs(app_data_dir=tmp_path / "app-data")

    pdf_path = fixture_dir / "malicious.pdf"
    visible_pdf = ensure_pdf_preview_copy(str(pdf_path), pdf_path.name)
    assert safe_pdf_page_count(visible_pdf) == 3
    assert "embed=1" in build_pdfjs_viewer_src(visible_pdf, 2)

    docx_html = extract_docx_html(str(fixture_dir / "malicious.docx"))
    assert "MARA DOCX SAFE TEXT" in docx_html
    assert "DOCX JS LINK" in docx_html
    assert "javascript:" not in docx_html
    assert "image/svg+xml" not in docx_html

    controller = SimpleNamespace(
        _non_pdf_preview_cache={},
        _total_pages_cache={},
    )
    service = PresentationPreviewService(controller)
    pptx_path = fixture_dir / "malicious.pptx"
    first_page = service.get_preview_src("malicious-pptx", str(pptx_path), 1)
    second_page = service.get_preview_src("malicious-pptx", str(pptx_path), 2)
    first_page = unquote(first_page)
    second_page = unquote(second_page)
    assert "PPTX JS LINK" in first_page
    assert "javascript:" not in first_page
    assert "image/svg+xml" not in first_page
    assert "MARA PPTX SLIDE TWO" in second_page
