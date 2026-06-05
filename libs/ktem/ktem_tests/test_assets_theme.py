from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
THEME_FILE = PACKAGE_ROOT / "assets" / "theme.py"
CSS_FILE = PACKAGE_ROOT / "assets" / "css" / "main.css"
CONTROL_FILE = PACKAGE_ROOT / "pages" / "chat" / "control.py"
CHAT_PAGE_FILE = PACKAGE_ROOT / "pages" / "chat" / "__init__.py"
CHAT_PANEL_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py"
MAIN_FILE = PACKAGE_ROOT / "main.py"
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


def _read_chat_page() -> str:
    return CHAT_PAGE_FILE.read_text(encoding="utf-8")


def _read_chat_panel() -> str:
    return CHAT_PANEL_FILE.read_text(encoding="utf-8")


def _read_main() -> str:
    return MAIN_FILE.read_text(encoding="utf-8")


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
    assert "#mara-shell-actions" in css
    assert "position: static;" in css
    assert "background: var(--app-surface-raised)" in css
    assert "#app-version-badge" in css


def test_css_applies_reading_surface_to_preview_and_evidence_cards():
    css = _read_css()

    assert "#main-pdf-preview" in css
    assert "#main-pdf-preview {\n  background: var(--reading-surface)" in css
    assert "#kg-answer-hint .kg-answer-hint__node" in css
    assert "background: var(--reading-surface" in css
    assert ".studio-artifacts-card" in css and ".notebook-panel-card" in css


def test_chat_page_uses_page_centric_workbench_layout():
    chat_page = _read_chat_page()
    chat_panel = _read_chat_panel()

    ask_panel_label = "right-ask-tabs"
    assert ask_panel_label in chat_page
    assert 'elem_id="answer-expand"' in chat_page
    assert 'with gr.Row(elem_id="page-workbench-layout"):' in chat_page
    assert 'with gr.Column(elem_id="info-expand"):' in chat_page
    assert "knowledge-map-title" in chat_page
    assert (
        "value=\"<div class='pdf-preview-notice'>Selected page preview.</div>\""
        in chat_panel
    )
    assert 'placeholder="Ask a question about the selected page"' in chat_panel
    assert "Vision Transformer (ViT)" not in chat_panel
    assert "Select a file and page to preview." in chat_panel

    assert chat_page.index(
        "self.chat_panel.render_notice_and_pager()"
    ) < chat_page.index("self.chat_panel.render_input()")
    assert chat_page.index(ask_panel_label) < chat_page.index(
        "self.chat_panel.render_input()"
    )
    assert chat_page.index("self.chat_panel.render_input()") < chat_page.index(
        "self.followup_questions = self.chat_suggestion.examples"
    )


def test_workbench_matches_reference_prototype_structure():
    chat_page = _read_chat_page()
    chat_panel = _read_chat_panel()
    main = _read_main()
    main_js = _read_main_js()

    expected_chat_tokens = [
        'elem_id="workbench-file-summary"',
        'elem_id="reader-workbench"',
        'elem_id="page-strip-panel"',
        'elem_id="document-reader-panel"',
        'elem_id="reader-toolbar"',
        'elem_id="page-metadata-strip"',
        'elem_id="citations-card"',
        'elem_id="reasoning-trace-card"',
        'elem_id="notebook-panel-card"',
        'elem_id="conversation-dock"',
        'elem_id="answer-expand"',
    ]
    for token in expected_chat_tokens:
        assert token in chat_page

    assert "render_preview_frame()" in chat_panel
    assert 'placeholder="Search files..."' in chat_page
    assert "right-ask-tabs" in chat_page
    assert 'label="Chat settings"' not in chat_page
    assert "refresh_page_context_view" in chat_page
    assert "_render_page_thumbnail_strip" in chat_page
    assert "self.page_strip_search = gr.State" in chat_page
    assert 'placeholder="Search within file..."' not in chat_page
    assert "refresh_page_thumbnail_search" not in chat_page
    assert "Suggested questions for this page" not in chat_page
    assert "_render_text_thumbnail_preview" in chat_page
    assert chat_page.index("right-ask-tabs") < chat_page.index("knowledge-map-title")

    for label in [
        '"chat"',
        '"files"',
        '"resources"',
        '"help"',
        '"settings"',
    ]:
        assert label in main
    for old_label in ['"Workbench"', '"Corpus"', '"Evaluation"']:
        assert old_label not in main
    assert 'elem_id="mara-status-bar"' in main
    assert 'elem_id="mara-user-identity-source"' in main
    assert "_render_user_identity_html" in main
    assert "GPT-4o" not in main
    assert "1,932 / 2,048" not in main
    assert "2.18 s" not in main
    assert "ensureMaraMasthead" in main_js
    assert "mara-brand-title" not in main_js
    assert "Multimodal Agentic Retrieval" not in main_js
    assert ">AK<" not in main_js
    assert "syncMaraAvatar" in main_js
    assert 'data-target-tab="indices-tab"' in main_js
    assert 'data-mara-action="search"' in main_js
    assert "data-reader-action='zoom-in'" in chat_page
    assert "bindReaderToolbarControls" in main_js
    assert "--reader-preview-zoom" in main_js
    assert "self._render_reasoning_trace_html()" in chat_page
    assert "self._render_citations_card_html()" in chat_page
    assert "render_studio_trace_panel" in chat_page
    assert "response.artifact" in chat_page
    assert "render_conversation_notebook_update" in chat_page
    assert "render_latest_reasoning_trace" in chat_page
    assert "render_latest_citations_card" in chat_page
    assert "Citations (3)" not in chat_page
    assert "Patch embedding definition" not in chat_page
    assert "Steps 4" not in chat_page
    assert "Query rewrite" not in chat_page
    assert "Rerank" not in chat_page


def test_chat_file_list_renders_corpus_style_cards():
    chat_page = _read_chat_page()

    expected_tokens = [
        "corpus-file-library",
        "corpus-file-section",
        "corpus-file-entry__icon",
        "corpus-file-entry__meta",
        "corpus-file-entry__status",
        "_format_corpus_file_type",
    ]
    for token in expected_tokens:
        assert token in chat_page


def test_txt_page_thumbnail_renders_text_preview_and_search_highlight():
    from types import SimpleNamespace
    from typing import Any, cast

    from ktem.pages.chat import ChatPage
    from ktem.pages.chat.page_preview_text import paginate_plain_text

    page = ChatPage.__new__(ChatPage)
    page.page_preview = cast(
        Any,
        SimpleNamespace(
            _extract_text_from_file=lambda _file_path, _file_name: (
                "alpha beta gamma\n" * 160
            ),
            _paginate_plain_text=paginate_plain_text,
        ),
    )

    rendered = page._render_page_thumbnail_strip(
        "txt-1", "notes.txt", "notes.txt", 1, 3, "gamma"
    )

    assert "page-thumbnail-card__text" in rendered
    assert "<mark>gamma</mark>" in rendered


def test_docx_page_thumbnail_renders_text_preview():
    from types import SimpleNamespace
    from typing import Any, cast

    from ktem.pages.chat import ChatPage
    from ktem.pages.chat.page_preview_text import paginate_plain_text

    page = ChatPage.__new__(ChatPage)
    page.page_preview = cast(
        Any,
        SimpleNamespace(
            _extract_text_from_file=lambda _file_path, _file_name: (
                "Executive summary and method development\n" * 80
            ),
            _paginate_plain_text=paginate_plain_text,
        ),
    )

    rendered = page._render_page_thumbnail_strip(
        "docx-1", "proposal.docx", "proposal.docx", 1, 2, "method"
    )

    assert "page-thumbnail-card__text" in rendered
    assert "<mark>method</mark>" in rendered
    assert "page-thumbnail-card__page" not in rendered


def test_user_avatar_initials_come_from_username():
    from ktem.main import App

    assert App._initials_from_username("alice kim") == "AK"
    assert App._initials_from_username("zhangsan") == "ZH"


def test_css_declares_page_workbench_layout_tokens():
    css = _read_css()

    expected_tokens = [
        "--page-preview-min-height: clamp(430px, calc(100vh - 430px), 720px);",
        "--page-preview-toolbar-height: 38px;",
        "--qa-panel-input-height: 46px;",
        "--workbench-left-width: 278px;",
        "--page-rail-width: 278px;",
        "--workbench-right-width: 430px;",
        "--workbench-column-gap-budget: 40px;",
        "--mara-topbar-height: 64px;",
        "--workbench-viewport-height:",
        "#mara-brand-lockup",
        "#page-workbench-layout",
        "#reader-workbench",
        "#page-strip-panel",
        "#document-reader-panel",
        "#reader-toolbar",
        "#page-metadata-strip",
        "#mara-status-bar",
        "#mara-user-identity-source",
        ".page-thumbnail-card__text",
        "position: fixed !important;",
        "#mara-shell-actions {\n  flex: 0 0 auto !important;",
        "white-space: nowrap !important;",
        "#chat-tab:has(#conv-settings-panel):has(#chat-area):has(#chat-info-panel)",
        "#chat-tab .gap:has(> #conv-settings-panel):has(> #chat-area):has(> #chat-info-panel)",
        "#chat-tab .gradio-row:has(> #conv-settings-panel):has(> #chat-area):has(> #chat-info-panel)",
        "#chat-area {\n  flex: 1 1 auto !important;",
        "#chat-info-panel {\n  flex: 0 0 var(--workbench-right-width) !important;",
        "min-height: var(--page-preview-min-height) !important;",
        "#answer-expand #chat-input-row",
        "#answer-expand #qa-scope",
        "#answer-expand #qa-scope .wrap",
        "flex-wrap: nowrap !important;",
        '#answer-expand #qa-scope label:has(input[type="radio"])',
        '#answer-expand #qa-scope label:has(input[type="radio"]) span',
        '#answer-expand #qa-scope input[type="radio"]',
        "white-space: nowrap !important;",
        "#answer-expand #chat-input",
        "#answer-expand #chat-input .scroll-hide",
        '#answer-expand #chat-input [data-testid="textbox"]',
        "@media (max-width: 1100px)",
        "grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));",
        ".reasoning-trace-card--empty",
    ]

    for token in expected_tokens:
        assert token in css


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
