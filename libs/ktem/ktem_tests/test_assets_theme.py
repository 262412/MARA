from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
THEME_FILE = PACKAGE_ROOT / "assets" / "theme.py"
CSS_FILE = PACKAGE_ROOT / "assets" / "css" / "main.css"
CONTROL_FILE = PACKAGE_ROOT / "pages" / "chat" / "control.py"
MAIN_JS_FILE = PACKAGE_ROOT / "assets" / "js" / "main.js"
RESOURCE_UI_FILES = [
    PACKAGE_ROOT / "index" / "ui.py",
    PACKAGE_ROOT / "llms" / "ui.py",
    PACKAGE_ROOT / "embeddings" / "ui.py",
    PACKAGE_ROOT / "rerankings" / "ui.py",
    PACKAGE_ROOT / "mcp" / "ui.py",
]


def _read_theme() -> str:
    return THEME_FILE.read_text(encoding="utf-8")


def _read_css() -> str:
    return CSS_FILE.read_text(encoding="utf-8")


def _read_control() -> str:
    return CONTROL_FILE.read_text(encoding="utf-8")


def _read_main_js() -> str:
    return MAIN_JS_FILE.read_text(encoding="utf-8")


def _read_resource_ui_files() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in RESOURCE_UI_FILES)


def test_theme_defaults_match_research_workbench_palette():
    theme = _read_theme()

    assert "primary_hue: colors.Color | str = colors.teal" in theme
    assert "secondary_hue: colors.Color | str = colors.sky" in theme
    assert 'fonts.GoogleFont("Plus Jakarta Sans")' in theme


def test_css_declares_semantic_research_palette():
    css = _read_css()

    expected_variables = [
        "--app-bg",
        "--app-surface",
        "--app-surface-raised",
        "--app-border",
        "--app-accent",
        "--app-accent-secondary",
        "--app-focus-ring",
        "--reading-surface",
        "--reading-border",
        "--graph-dark-surface",
    ]

    for variable in expected_variables:
        assert variable in css


def test_light_palette_is_soft_gray_not_plain_white():
    css = _read_css()

    assert "--app-bg: #edf2f7;" in css
    assert "--app-surface: #f8fafc;" in css
    assert "--app-surface-raised: #f3f6fa;" in css
    assert "Theme Override: match provided dark-indigo gradient reference UI" not in css
    assert "--theme-panel-glass" not in css
    assert ".gradio-container label" in css
    assert "--block-border-color: var(--app-border);" in css
    assert '[data-testid="block-info"]' in css
    assert ".gradio-container .form" in css
    assert "#ktem-theme-toggle" in css
    assert "top: 15px;" in css
    assert "background: var(--app-surface-raised)" in css
    assert "#app-version-badge" in css
    assert "position: absolute" in css
    assert "top: -2px;" in css


def test_css_applies_reading_surface_to_preview_and_evidence_cards():
    css = _read_css()

    assert "#main-pdf-preview" in css
    assert "#main-pdf-preview {\n  background: var(--reading-surface)" in css
    assert "#kg-answer-hint .kg-answer-hint__node" in css
    assert "background: var(--reading-surface" in css


def test_css_preserves_graph_lab_dark_theme_hooks():
    css = _read_css()

    assert "body.dark .gradio-container" in css
    assert "body.ktem-dark-mode .gradio-container" in css
    assert "--graph-dark-surface" in css
    assert "#knowledge-graph-plot .kg-preview-card" in css
    assert "var(--graph-dark-surface)" in css


def test_management_pages_use_consistent_scrollable_frames():
    css = _read_css()

    expected_tokens = [
        "--management-frame-max-height: clamp(320px, 52vh, 560px);",
        "--management-field-max-height: clamp(240px, 42vh, 460px);",
        '#indices-tab [role="grid"].table-wrap',
        '#resources-tab [role="grid"].table-wrap',
        "#indices-tab .gradio-textbox textarea",
        "#resources-tab .gradio-textbox textarea",
        "#indices-tab .cm-editor",
        "#resources-tab .cm-editor",
        "#indices-tab .cm-scroller",
        "#resources-tab .cm-scroller",
        "#indices-tab .gradio-markdown:has(h1)",
        "#resources-tab .gradio-markdown:has(table)",
        "#indices-tab .gradio-markdown:has(pre)",
        "#resources-tab .gradio-markdown:has(code)",
        '#indices-tab [data-testid="markdown"]:has(h1)',
        '#resources-tab [data-testid="markdown"]:has(table)',
        "#indices-tab .gradio-html",
        "#resources-tab .gradio-html",
        "table-layout: auto !important;",
        "width: 100% !important;",
        "max-width: 100% !important;",
        "box-sizing: border-box;",
        "min-width: 0 !important;",
        "overflow-wrap: anywhere;",
        "word-break: break-word;",
        "overflow: auto !important;",
        "overflow: hidden !important;",
        "resize: vertical;",
        "display: block !important;",
        "text-align: left !important;",
    ]

    for token in expected_tokens:
        assert token in css

    assert "height: var(--management-frame-height)" not in css
    assert "min-height: var(--management-frame-height)" not in css
    assert "width: max-content !important;" not in css
    assert "table-layout: fixed !important;" not in css
    management_blocks = [
        block
        for block in css.split("}")
        if "#indices-tab" in block or "#resources-tab" in block
    ]
    assert all(
        "white-space: nowrap !important;" not in block for block in management_blocks
    )
    assert "white-space: pre;" not in css
    assert "#indices-tab .cm-content" not in css
    assert "#resources-tab .cm-content" not in css
    assert "#indices-tab .gradio-markdown .prose" not in css
    assert "#resources-tab .gradio-markdown .prose" not in css
    assert "#indices-tab .gradio-html > div" not in css
    assert "#resources-tab .gradio-html > div" not in css


def test_management_tables_keep_row_separation_and_detail_scrolling():
    css = _read_css()
    resource_ui = _read_resource_ui_files()

    expected_css_tokens = [
        "--management-detail-max-height: clamp(260px, calc(100vh - 430px), 520px);",
        "#indices-tab,\n#resources-tab {\n  overflow: auto !important;",
        "#resources-tab .management-detail-panel",
        "max-height: var(--management-detail-max-height) !important;",
        "overscroll-behavior: contain;",
        "#resources-tab .management-detail-panel .gradio-markdown",
        '#indices-tab [role="grid"].table-wrap tbody tr:nth-child(even) td',
        '#resources-tab [role="grid"].table-wrap tbody tr:nth-child(even) td',
        "#file_list_view tbody tr:nth-child(even) td",
        '#resources-tab [role="grid"].table-wrap tbody tr:hover td',
        "border-bottom: 1px solid var(--app-border) !important;",
        "border-right: 1px solid var(--app-border) !important;",
    ]

    for token in expected_css_tokens:
        assert token in css

    assert resource_ui.count('elem_classes=["management-detail-panel"]') >= 5
    assert "--management-detail-max-height: min(680px, calc(100vh - 190px));" not in css


def test_rounded_controls_keep_text_inside_their_backgrounds():
    css = _read_css()

    expected_tokens = [
        "/* Rounded controls: keep labels away from curved borders and prevent spillover. */",
        ".gradio-container .tab-nav button",
        '.gradio-container [role="tab"]',
        ".gradio-container .gr-button",
        ".gradio-container .block-label",
        '.gradio-container [data-testid="block-label"]',
        "#info-expand-button.no-background",
        "#rename-conv-button.no-background",
        "#new-conv-button.no-background",
        "box-sizing: border-box !important;",
        "max-width: 100% !important;",
        "min-width: 0 !important;",
        "padding: 8px 14px !important;",
        "line-height: 1.35 !important;",
        "white-space: normal !important;",
        "overflow-wrap: anywhere;",
        "word-break: break-word;",
        ".gradio-container .tab-nav button",
        "padding: 8px 16px !important;",
        "padding: 0 !important;",
        '#indices-tab [role="grid"].table-wrap button',
        "padding: 6px 8px !important;",
    ]

    for token in expected_tokens:
        assert token in css

    assert "text-overflow: clip;" in css
    assert "overflow: visible;" in css


def test_pdf_pager_keeps_page_number_background_uniform():
    css = _read_css()

    expected_tokens = [
        "/* PDF pager: keep the page number control visually flat inside the preview toolbar. */",
        "#pdf-preview-notice,\n#pdf-pager-row",
        "#pdf-pager-row > div",
        "#pdf-pager-row .block",
        "#pdf-page-number",
        "#pdf-page-number .wrap",
        "#pdf-page-number .wrap-inner",
        "background: transparent !important;",
        "border-color: transparent !important;",
        "box-shadow: none !important;",
        '#pdf-page-number input[type="number"]',
        "background: var(--app-surface) !important;",
        "border: 1px solid var(--app-border) !important;",
        "padding: 0 12px !important;",
        "appearance: textfield;",
        "-moz-appearance: textfield;",
        '#pdf-page-number input[type="number"]::-webkit-outer-spin-button',
        '#pdf-page-number input[type="number"]::-webkit-inner-spin-button',
        "-webkit-appearance: none;",
    ]

    for token in expected_tokens:
        assert token in css


def test_radio_selected_state_is_visually_prominent_across_pages():
    css = _read_css()

    expected_tokens = [
        "/* Radio choices: make selected pills obvious across chat, files, settings, and setup pages. */",
        '.gradio-container label:has(input[type="radio"])',
        ".gradio-container .gradio-radio label",
        '.gradio-container label.selected:has(input[type="radio"])',
        '.gradio-container label:has(input[type="radio"][aria-checked="true"])',
        ".gradio-container .gradio-radio label.selected",
        "background: linear-gradient(",
        "border-color: var(--app-accent) !important;",
        "color: var(--app-accent-strong) !important;",
        "font-weight: 600 !important;",
        "box-shadow: 0 0 0 2px var(--app-focus-ring)",
        "accent-color: var(--app-accent);",
        "outline: 2px solid var(--app-accent);",
        "outline-offset: 2px;",
    ]

    for token in expected_tokens:
        assert token in css

    assert "font-weight: 700 !important;" not in css


def test_chat_radio_scope_does_not_shift_or_show_separator_before_input():
    css = _read_css()

    expected_tokens = [
        "/* Chat input row: rebuilt as radio choices plus a separate composer. */",
        "#chat-input-row {\n  display: grid !important;\n  grid-template-columns: minmax(0, 1fr) !important;",
        "gap: 10px !important;",
        "overflow: visible !important;",
        "#qa-scope {\n  display: block !important;",
        "padding: 0 !important;",
        "border: 0 !important;",
        "border-color: transparent !important;",
        "border-radius: 0 !important;",
        "box-shadow: none !important;",
        "#qa-scope .wrap {\n  display: flex !important;",
        "flex-wrap: wrap !important;",
        '#qa-scope label:has(input[type="radio"])',
        "flex: 0 0 auto !important;",
        "min-height: 34px;",
        "padding: 7px 12px !important;",
        "#chat-input {\n  display: block !important;",
        "border: 0 !important;",
        "border-radius: 0 !important;",
        "#chat-input > label,\n#chat-input label,\n#chat-input > div,",
        "overflow: visible !important;",
        '#chat-input [aria-label="Upload files"],',
        '#chat-input [data-testid="file-upload"],',
        '#chat-input [data-testid="upload-button"]',
        "position: absolute !important;",
        "display: none !important;",
        "opacity: 0 !important;",
        "#chat-input .input-container {\n  display: grid !important;",
        "grid-template-columns: minmax(0, 1fr) 44px !important;",
        "column-gap: 8px !important;",
        "background: transparent !important;",
        "border: 0 !important;",
        "border-radius: 0 !important;",
        "overflow: visible !important;",
        '#chat-input .scroll-hide,\n#chat-input [data-testid="textbox"]',
        "height: 42px !important;",
        "padding: 10px 14px !important;",
        "border: 1px solid var(--app-border) !important;",
        "border-radius: 999px !important;",
        "box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05) !important;",
        "white-space: nowrap !important;",
        "overflow-y: hidden !important;",
        "#chat-input .submit-button {\n  grid-column: 2 !important;",
        "height: 42px !important;",
        "width: 44px !important;",
        "border: 1px solid var(--app-border) !important;",
        "border-radius: 999px !important;",
        "box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05) !important;",
    ]

    for token in expected_tokens:
        assert token in css


def test_dark_light_toggle_is_visible_and_wired():
    control = _read_control()
    css = _read_css()
    main_js = _read_main_js()

    assert "toggle-dark-button" not in control
    assert "toggle-dark-button" not in css
    assert "toggle-dark-button" not in main_js
    assert 'darkToggle.style.display = "none"' not in main_js
    assert "ktem-ui-mode" in main_js
    assert "ktem-theme-toggle" in main_js
    assert "ensureGlobalThemeToggle" in main_js
    assert "ktem-dark-mode" in main_js
