from pathlib import Path

CSS_FILE = Path(__file__).resolve().parents[1] / "ktem" / "assets" / "css" / "main.css"


def test_studio_artifact_picker_cards_and_detail_panel_are_styled():
    css = CSS_FILE.read_text(encoding="utf-8")
    detail_panel_css = _css_block(css, "#studio-artifact-detail-panel")

    assert ".studio-artifact-card-grid" in css
    assert "#studio-artifact-detail-panel" in css
    assert "position: fixed !important;" in css
    assert "z-index: 1600 !important;" in css
    assert "background: var(--app-surface) !important;" in detail_panel_css
    assert "display:" not in detail_panel_css
    assert ".studio-artifact-card-button" in css


def test_studio_artifact_detail_panel_sits_above_workbench_dividers_without_transform():
    css = CSS_FILE.read_text(encoding="utf-8")
    chat_info_css = _css_block(css, "#chat-info-panel")
    detail_panel_css = _css_block(css, "#studio-artifact-detail-panel")

    assert "z-index: 20 !important;" in chat_info_css
    assert "left: 0 !important;" in detail_panel_css
    assert "right: 0 !important;" in detail_panel_css
    assert "margin: 0 auto !important;" in detail_panel_css
    assert "transform:" not in detail_panel_css
    assert "overflow: visible !important;" in detail_panel_css


def test_studio_artifact_detail_backdrop_blurs_and_dims_page_background():
    css = CSS_FILE.read_text(encoding="utf-8")
    backdrop_css = _css_block(css, "#studio-artifact-overlay-backdrop")
    veil_css = _css_block(css, ".studio-artifact-overlay-backdrop__veil")

    assert "#studio-artifact-overlay-backdrop" in css
    assert "position: fixed !important;" in backdrop_css
    assert "inset: 0 !important;" in backdrop_css
    assert "z-index: 1590 !important;" in backdrop_css
    assert "backdrop-filter: blur(16px) saturate(70%) brightness(70%);" in backdrop_css
    assert (
        "-webkit-backdrop-filter: blur(16px) saturate(70%) brightness(70%);"
        in backdrop_css
    )
    assert "background: rgb(8 17 31 / 72%) !important;" in backdrop_css
    assert (
        "box-shadow: inset 0 0 0 9999px rgb(8 17 31 / 18%) !important;" in backdrop_css
    )
    assert "position: fixed !important;" in veil_css
    assert "inset: 0 !important;" in veil_css
    assert "z-index: 1590 !important;" in veil_css


def test_studio_artifact_detail_form_controls_are_labeled_and_aligned():
    css = CSS_FILE.read_text(encoding="utf-8")
    parameter_row_css = _css_block(css, "#studio-artifact-parameter-row")
    dropdown_options_css = _css_block(css, "#studio-artifact-detail-panel .options")
    count_input_css = _css_block(css, "#studio-artifact-count input")

    assert "align-items: end !important;" in parameter_row_css
    assert "overflow: visible !important;" in parameter_row_css
    assert "z-index: 1705 !important;" in dropdown_options_css
    assert "height: 44px !important;" in count_input_css
    assert "min-height: 44px !important;" in count_input_css


def _css_block(css: str, selector: str) -> str:
    start = css.index(selector)
    open_brace = css.index("{", start)
    close_brace = css.index("}", open_brace)
    return css[open_brace + 1 : close_brace]
