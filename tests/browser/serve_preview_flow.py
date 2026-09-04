"""Focused real-Gradio preview harness using production preview renderers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
from ktem.app import compose_blocks_js
from ktem.assets.pdfjs_assets import materialize_pdfjs
from ktem.pages.chat.chat_panel import ChatPanel
from ktem.pages.chat.page_preview_document import extract_docx_html, paginate_docx_html
from ktem.pages.chat.page_preview_presentation import PresentationPreviewService
from ktem.pages.chat.page_preview_runtime import (
    build_pdfjs_viewer_src,
    ensure_pdf_preview_copy,
    notice_html,
    safe_pdf_page_count,
)
from ktem.pages.chat.page_preview_text import build_html_pages
from ktem.preview.allowed_paths import build_gradio_allowed_paths


def _blocks_javascript(pdfjs_dir: Path) -> str:
    asset_root = Path(__file__).resolve().parents[2] / "libs/ktem/ktem/assets/js"
    safe_dom = (asset_root / "safe_dom.js").read_text(encoding="utf-8")
    main_js = (asset_root / "main.js").read_text(encoding="utf-8")
    viewer_path = f"/file={pdfjs_dir / 'web/viewer.html'}".replace("\\", "/")
    return (
        compose_blocks_js(main_js, safe_dom)
        .replace(
            "KTEM_PDFJS_VIEWER_PATH",
            repr(viewer_path),
        )
        .replace("KH_APP_VERSION", "browser-test")
    )


def _presentation_service():
    controller = SimpleNamespace(
        _non_pdf_preview_cache={},
        _total_pages_cache={},
    )
    return PresentationPreviewService(controller), controller


def _render_source(file_name: str, file_path: str, page: int):
    path = Path(str(file_path or ""))
    requested_page = max(1, int(page or 1))
    if not file_name or not path.is_file():
        return "", notice_html("Selected file is unavailable."), 1, 1
    try:
        if path.suffix.lower() == ".pdf":
            preview_path = ensure_pdf_preview_copy(str(path), file_name)
            total = safe_pdf_page_count(preview_path, 1)
            selected = min(requested_page, total)
            return (
                build_pdfjs_viewer_src(preview_path, selected),
                notice_html(""),
                total,
                selected,
            )
        if path.suffix.lower() == ".docx":
            rich_html = extract_docx_html(str(path))
            pages = build_html_pages(paginate_docx_html(rich_html))
        elif path.suffix.lower() == ".pptx":
            service, controller = _presentation_service()
            first = service.get_preview_src(str(path), str(path), 1)
            pages = controller._non_pdf_preview_cache.get(str(path), [])
            if first and not pages:
                pages = [first]
        else:
            pages = []
    except (OSError, ValueError, KeyError) as exc:
        return (
            "",
            notice_html(f"PREVIEW_SOURCE_ERROR preview_render internal: {exc}"),
            1,
            1,
        )
    if not pages:
        return (
            "",
            notice_html(f"PREVIEW_SOURCE_ERROR preview_render internal: {file_name}"),
            1,
            1,
        )
    selected = min(requested_page, len(pages))
    return pages[selected - 1], notice_html(""), len(pages), selected


def create_app(pdfjs_dir: Path):
    with gr.Blocks(
        js=_blocks_javascript(pdfjs_dir),
        css="#main-pdf-preview{height:620px} .pdf-preview-shell{height:100%}",
        analytics_enabled=False,
    ) as demo:
        gr.Markdown("# MARA Preview Security Flow")
        upload = gr.File(label="Upload preview fixture", elem_id="preview-upload")
        selector = gr.Dropdown(
            choices=[],
            label="Source",
            elem_id="preview-source-selector",
        )
        active_path = gr.State("")
        total_pages = gr.State(1)
        panel = ChatPanel(SimpleNamespace(app_name="MARA preview harness"))
        panel.render_notice_and_pager()

        def receive_upload(value):
            path = str(value or "")
            original_name = str(getattr(value, "orig_name", "") or "")
            name = Path(original_name or path).name if path else ""
            return gr.update(choices=[name] if name else [], value=None), path

        upload.upload(
            receive_upload,
            inputs=upload,
            outputs=[selector, active_path],
        )
        selector.change(
            _render_source,
            inputs=[selector, active_path, panel.page_number],
            outputs=[
                panel.pdf_preview_src,
                panel.pdf_preview_notice,
                total_pages,
                panel.page_number,
            ],
        )
        panel.page_number.change(
            _render_source,
            inputs=[selector, active_path, panel.page_number],
            outputs=[
                panel.pdf_preview_src,
                panel.pdf_preview_notice,
                total_pages,
                panel.page_number,
            ],
        )
    return demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    app_data = Path(os.environ["KH_APP_DATA_DIR"])
    pdfjs_dir = materialize_pdfjs(app_data_dir=app_data).path
    gradio_temp = Path(os.environ["GRADIO_TEMP_DIR"])
    (app_data / "private.txt").write_text("private", encoding="utf-8")
    other_version = app_data / "assets/pdfjs/other-version"
    other_version.mkdir(parents=True, exist_ok=True)
    (other_version / "secret.txt").write_text("other-version", encoding="utf-8")
    gradio_temp.mkdir(parents=True, exist_ok=True)
    file_storage = app_data / "files"
    file_storage.mkdir(parents=True, exist_ok=True)
    (file_storage / "victim.pdf").write_bytes(b"not-visible")
    docs = Path(__file__).resolve().parents[2] / "docs"
    create_app(pdfjs_dir).queue().launch(
        server_name="127.0.0.1",
        server_port=args.port,
        inbrowser=False,
        show_error=True,
        allowed_paths=build_gradio_allowed_paths(
            pdfjs_dir=pdfjs_dir,
            gradio_temp_dir=gradio_temp,
            doc_dir=docs,
        ),
    )


if __name__ == "__main__":
    main()
