import re
from pathlib import Path


def _main_css() -> str:
    package_root = Path(__file__).resolve().parents[1] / "ktem"
    return (package_root / "assets" / "css" / "main.css").read_text(encoding="utf-8")


def _block_after(css: str, selector: str) -> str:
    start = css.index(selector)
    return css[start : css.index("}", start)]


def test_global_ui_uses_quiet_aurora_motion_tokens_without_layout_changes():
    css = _main_css()

    for token in [
        "--motion-fast: 140ms;",
        "--motion-base: 220ms;",
        "--motion-slow: 360ms;",
        "--motion-ease: cubic-bezier(0.16, 1, 0.3, 1);",
        "--app-accent-tertiary:",
        "--app-gradient-thinking:",
        "--app-gradient-surface:",
        "--app-gradient-ambient:",
        "--app-ambient-opacity:",
        "--app-shimmer-duration:",
        "--app-flow-duration:",
        ".app-shimmer-text",
        ".gradio-container::before",
        "#chat-tab::before",
        "#indices-tab::before",
        "#resources-tab::before",
        "#chat-tab.tabitem",
        "@keyframes app-page-enter",
        "@keyframes app-ambient-flow",
        "@keyframes app-tab-aurora",
        "@keyframes app-shimmer-sweep",
        "animation: app-page-enter var(--motion-slow) var(--motion-ease) both;",
        "animation: app-tab-aurora calc(var(--app-flow-duration) * 2.4) var(--motion-ease) infinite alternate;",
        "background: var(--app-gradient-thinking);",
        "background: var(--app-gradient-ambient);",
        "transition-duration: var(--motion-base) !important;",
        "transition-timing-function: var(--motion-ease) !important;",
        "motion-reduce",
    ]:
        assert token in css

    reduced_motion_css = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    for token in [
        ".app-shimmer-text",
        ".gradio-container::before",
        "#chat-tab::before",
        "animation: none !important;",
        "transition-duration: 1ms !important;",
    ]:
        assert token in reduced_motion_css


def test_workbench_surfaces_carry_visible_aurora_above_base_background():
    css = _main_css()

    for token in [
        "#conv-settings-panel::before",
        "#chat-area::before",
        "#page-strip-panel::before",
        "#document-reader-panel::before",
        "#chat-info-panel::before",
        "#mara-status-bar::before",
    ]:
        assert token in css

    surface_aurora_block = _block_after(css, "#conv-settings-panel::before,")
    for token in [
        "background: var(--app-gradient-ambient);",
        "animation: app-tab-aurora",
        "opacity: 0.3;",
        "z-index: 0;",
    ]:
        assert token in surface_aurora_block

    for selector in [
        "#conv-settings-panel",
        "#chat-area",
        "#page-strip-panel",
        "#document-reader-panel",
        "#chat-info-panel",
    ]:
        panel_block = _block_after(css, f"{selector},")
        assert "position: relative !important;" in panel_block
        assert "isolation: isolate;" in panel_block


def test_dark_mode_tokens_and_non_chat_pages_do_not_fall_back_to_light_surfaces():
    css = _main_css()

    for token in [
        "html.dark",
        "html.ktem-dark-mode",
        "body.dark",
        "body.ktem-dark-mode",
        "html.dark .gradio-container",
        "html.ktem-dark-mode .gradio-container",
        "body.dark .gradio-container",
        "body.ktem-dark-mode .gradio-container",
        ".gradio-container.dark",
    ]:
        assert token in css

    dark_token_block = _block_after(css, "html.dark,\nhtml.ktem-dark-mode,")
    for token in [
        "--app-bg: #08111f;",
        "--app-surface: #0f172a;",
        "--app-surface-raised: #111c2e;",
        "--app-surface-muted: #1e293b;",
        "--app-accent: #2dd4bf;",
        "--app-accent-secondary: #38bdf8;",
        "--app-accent-tertiary: #a78bfa;",
        "--app-text: #f8fafc;",
    ]:
        assert token in dark_token_block
    for light_token in [
        "--app-bg: #d2dde8;",
        "--app-surface-raised: #f3f8fc;",
        "--app-text: #142033;",
    ]:
        assert light_token not in dark_token_block

    for token in [
        "html.dark #indices-tab",
        "html.dark #resources-tab",
        "html.dark #help-tab",
        "html.dark #settings-tab",
        ".gradio-container.dark #indices-tab",
        ".gradio-container.dark #resources-tab",
        "body.dark #indices-tab",
        "body.dark #resources-tab",
        "body.dark #help-tab",
        "body.dark #settings-tab",
        "body.dark #indices-tab .block",
        "body.dark #resources-tab .block",
        "body.dark #help-tab .block",
        "body.dark #settings-tab .block",
        "body.dark #indices-tab form",
        "body.dark #resources-tab form",
        "body.dark #help-tab form",
        "body.dark #settings-tab form",
        "body.dark #indices-tab .gradio-markdown",
        "body.dark #resources-tab .gradio-markdown",
        "body.dark #help-tab .gradio-markdown",
        "body.dark #settings-tab .gradio-markdown",
        "body.dark .gradio-container::before",
        "background: var(--app-gradient-ambient);",
    ]:
        assert token in css


def test_dark_mode_selected_controls_use_theme_tokens():
    css = _main_css()

    for token in [
        "html.dark button.selected",
        "html.dark .header-bar button.selected",
        "html.dark .gradio-container button.selected",
        'html.dark .gradio-container button[aria-selected="true"]',
        "html.dark #indices-tab .tab-nav button.selected",
        'html.dark #indices-tab .tab-nav button[aria-selected="true"]',
        ".gradio-container.dark button.selected",
        "body.dark button.selected",
        "body.dark .header-bar button.selected",
        "body.dark .gradio-container button.selected",
        'body.dark .gradio-container button[aria-selected="true"]',
        "body.dark .gradio-container .tab-nav button.selected",
        'body.dark .gradio-container .tab-nav button[aria-selected="true"]',
        "html.ktem-dark-mode button.selected",
        "html.ktem-dark-mode .header-bar button.selected",
        "html.ktem-dark-mode .gradio-container button.selected",
        'html.ktem-dark-mode .gradio-container button[aria-selected="true"]',
        "html.ktem-dark-mode .gradio-container .tab-nav button.selected",
        'html.ktem-dark-mode .gradio-container .tab-nav button[aria-selected="true"]',
    ]:
        assert token in css

    dark_selected_block = _block_after(css, "body.dark button.selected,")
    for token in [
        "background: var(--control-bg-selected) !important;",
        "border-color: var(--control-border-selected) !important;",
        "color: var(--control-text-selected) !important;",
        "box-shadow: var(--control-shadow-selected) !important;",
    ]:
        assert token in dark_selected_block
    assert "#fff" not in dark_selected_block
    assert "var(--background-fill-primary" not in dark_selected_block


def test_buttons_have_distinct_default_hover_and_selected_states():
    css = _main_css()

    default_block = _block_after(css, ".gradio-container button,")
    for token in [
        "background: var(--control-bg-default) !important;",
        "color: var(--control-text-default) !important;",
        "box-shadow: var(--control-shadow-default) !important;",
    ]:
        assert token in default_block
    for token in [
        ".gradio-container button.primary",
        ".gradio-container button.secondary",
    ]:
        assert token in css
    assert "var(--app-gradient-surface)" not in default_block

    hover_block = _block_after(
        css,
        ".gradio-container button:not(:disabled):hover,",
    )
    assert "background: var(--control-bg-hover) !important;" in hover_block
    assert "box-shadow: var(--control-shadow-hover) !important;" in hover_block

    selected_block = _block_after(css, ".gradio-container button.selected,")
    for token in [
        "background: var(--control-bg-selected) !important;",
        "color: var(--control-text-selected) !important;",
        "box-shadow: var(--control-shadow-selected) !important;",
    ]:
        assert token in selected_block


def test_selected_controls_share_semantic_tokens_across_navigation_layers():
    css = _main_css()

    for token in [
        "--control-bg-default:",
        "--control-bg-hover:",
        "--control-bg-selected:",
        "--control-text-default:",
        "--control-text-hover:",
        "--control-text-selected:",
        "--control-border-default:",
        "--control-border-hover:",
        "--control-border-selected:",
        "--control-shadow-hover:",
        "--control-shadow-selected:",
        "--nav-control-bg-default:",
    ]:
        assert token in css

    default_block = _block_after(css, ".gradio-container button,")
    for token in [
        "background: var(--control-bg-default) !important;",
        "border: 1px solid var(--control-border-default) !important;",
        "color: var(--control-text-default) !important;",
        "box-shadow: var(--control-shadow-default) !important;",
    ]:
        assert token in default_block
    assert "var(--control-bg-hover)" not in default_block
    assert "var(--control-bg-selected)" not in default_block

    hover_block = _block_after(
        css,
        ".gradio-container button:not(:disabled):hover,",
    )
    for token in [
        "background: var(--control-bg-hover) !important;",
        "border-color: var(--control-border-hover) !important;",
        "box-shadow: var(--control-shadow-hover) !important;",
        "color: var(--control-text-hover) !important;",
    ]:
        assert token in hover_block

    selected_block = _block_after(css, ".gradio-container button.selected,")
    for token in [
        "background: var(--control-bg-selected) !important;",
        "border-color: var(--control-border-selected) !important;",
        "color: var(--control-text-selected) !important;",
        "box-shadow: var(--control-shadow-selected) !important;",
    ]:
        assert token in selected_block

    header_selected_blocks = re.findall(
        r"\.header-bar button\.selected\s*\{[^}]+\}",
        css,
    )
    assert header_selected_blocks
    for block in header_selected_blocks:
        for token in [
            "background: var(--control-bg-selected) !important;",
            "border-color: var(--control-border-selected) !important;",
            "color: var(--control-text-selected) !important;",
            "box-shadow: var(--control-shadow-selected) !important;",
        ]:
            assert token in block
        assert "background: transparent !important;" not in block
        assert "border-bottom:" not in block

    dark_selected_block = _block_after(css, "body.dark button.selected,")
    for token in [
        "background: var(--control-bg-selected) !important;",
        "border-color: var(--control-border-selected) !important;",
        "color: var(--control-text-selected) !important;",
        "box-shadow: var(--control-shadow-selected) !important;",
    ]:
        assert token in dark_selected_block


def test_active_toolbar_and_segmented_controls_use_selected_tokens():
    css = _main_css()

    for selector in [
        ".reader-toolbar button.is-active",
        ".right-ask-tabs button.is-active",
        '.gradio-container label.selected:has(input[type="radio"])',
    ]:
        block = _block_after(css, selector)
        for token in [
            "background: var(--control-bg-selected) !important;",
            "border-color: var(--control-border-selected) !important;",
            "color: var(--control-text-selected) !important;",
            "box-shadow: var(--control-shadow-selected) !important;",
        ]:
            assert token in block
        assert "#0f8b8d" not in block
        assert "border-bottom:" not in block


def test_dark_mode_tab_wrappers_and_aurora_use_theme_tokens():
    css = _main_css()

    for token in [
        "body.dark #indices-tab .wrap",
        "body.dark #resources-tab .wrap",
        "body.dark #help-tab .wrap",
        "body.dark #settings-tab .wrap",
        "body.dark #indices-tab .gap",
        "body.dark #resources-tab .gap",
        "body.dark #help-tab .gap",
        "body.dark #settings-tab .gap",
        "body.dark #indices-tab .gradio-row",
        "body.dark #resources-tab .gradio-row",
        "body.dark #indices-tab .gradio-column",
        "body.dark #resources-tab .gradio-column",
        "body.dark #indices-tab .tabs",
        "body.dark #resources-tab .tabs",
        "body.dark #indices-tab .tabitem",
        "body.dark #resources-tab .tabitem",
        "html.ktem-dark-mode #indices-tab .wrap",
        "html.ktem-dark-mode #resources-tab .wrap",
        "html.ktem-dark-mode #indices-tab .tabitem",
        "html.ktem-dark-mode #resources-tab .tabitem",
    ]:
        assert token in css

    wrapper_block = _block_after(css, "html.ktem-dark-mode #indices-tab .wrap,")
    assert "background: transparent !important;" in wrapper_block
    assert "color: var(--app-text) !important;" in wrapper_block

    surface_block = _block_after(css, "html.ktem-dark-mode #indices-tab .block,")
    assert "background: var(--app-surface) !important;" in surface_block

    for token in [
        "body.dark #chat-tab::before",
        "body.dark #indices-tab::before",
        "body.dark #resources-tab::before",
        "body.dark #help-tab::before",
        "body.dark #settings-tab::before",
        "html.ktem-dark-mode #chat-tab::before",
        "html.ktem-dark-mode #indices-tab::before",
        "html.ktem-dark-mode #resources-tab::before",
        "html.ktem-dark-mode #help-tab::before",
        "html.ktem-dark-mode #settings-tab::before",
    ]:
        assert token in css

    dark_aurora_block = _block_after(css, "body.dark #chat-tab::before,")
    assert "opacity: 0.58;" in dark_aurora_block
    assert "filter: saturate(1.18);" in dark_aurora_block
