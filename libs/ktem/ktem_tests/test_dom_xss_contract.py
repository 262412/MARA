from pathlib import Path
from urllib.parse import unquote

from ktem.pages.chat.page_preview_text import build_html_pages

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"


def _asset_source(name: str) -> str:
    return (PACKAGE_ROOT / "assets" / "js" / name).read_text(encoding="utf-8")


def _decode_data_html(uri: str) -> str:
    return unquote(uri.split(",", 1)[1])


def test_preview_iframes_have_minimal_sandbox_and_no_referrer_policy():
    chat_panel = (PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py").read_text(
        encoding="utf-8"
    )
    pdf_viewer = _asset_source("pdf_viewer.js")

    assert "sandbox='allow-same-origin'" in chat_panel
    assert "referrerpolicy='no-referrer'" in chat_panel
    assert 'KtemSafeDom.setIframePolicy(pdfViewer, "pdf")' in pdf_viewer
    for forbidden in (
        "allow-forms",
        "allow-popups",
        "allow-popups-to-escape-sandbox",
        "allow-top-navigation",
    ):
        assert forbidden not in chat_panel
        assert forbidden not in pdf_viewer


def test_app_loads_safe_dom_helper_before_main_and_pdf_viewer():
    app_source = (PACKAGE_ROOT / "app.py").read_text(encoding="utf-8")

    assert 'dir_assets / "js" / "safe_dom.js"' in app_source
    assert "self._safe_dom_js" in app_source
    assert "self._safe_dom_js" in app_source.split("compose_blocks_js", 2)[-1]


def test_plain_document_preview_csp_blocks_scripts_and_remote_content():
    uri = build_html_pages(
        [
            '<p><img src="https://attacker.invalid/x" onerror="parent.__xss=1">'
            "</p><script>parent.__xss=2</script>"
        ]
    )[0]
    html = _decode_data_html(uri)

    assert "Content-Security-Policy" in html
    assert "default-src 'none'" in html
    assert "script-src 'none'" in html
    assert "img-src data: blob:" in html


def test_document_preview_never_embeds_inline_script_capability():
    uri = build_html_pages(["<p>presentation text</p>"])[0]
    html = _decode_data_html(uri)

    assert uri.startswith("data:text/html;charset=utf-8,")
    assert "ktem-scripted" not in uri
    assert "script-src 'none'" in html
    assert "<script" not in html
    presentation_source = (
        PACKAGE_ROOT / "pages" / "chat" / "page_preview_presentation.py"
    ).read_text(encoding="utf-8")
    assert "_build_preview_script" not in presentation_source
