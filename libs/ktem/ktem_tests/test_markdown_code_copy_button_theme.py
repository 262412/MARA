from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
CSS_FILE = PACKAGE_ROOT / "assets" / "css" / "main.css"


def test_markdown_code_copy_buttons_keep_visible_icons():
    css = CSS_FILE.read_text(encoding="utf-8")

    expected_tokens = [
        ".gradio-container .code_wrap .copy_code_button",
        ".gradio-container .code_wrap .copy_code_button .copy-text",
        ".gradio-container .code_wrap .copy_code_button .check",
        ".gradio-container .code_wrap .copy_code_button svg",
        "width: 18px !important;",
        "height: 18px !important;",
        "color: var(--app-text) !important;",
        "background: color-mix(in srgb, var(--app-surface-raised) 90%, transparent) !important;",
    ]

    for token in expected_tokens:
        assert token in css
