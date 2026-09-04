from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
CHAT_PAGE_FILE = PACKAGE_ROOT / "pages" / "chat" / "__init__.py"
CHAT_LAYOUT_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_layout.py"
CHAT_PANEL_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py"
MAIN_FILE = PACKAGE_ROOT / "main.py"
MAIN_JS_FILE = PACKAGE_ROOT / "assets" / "js" / "main.js"


def _read_chat_page() -> str:
    return CHAT_PAGE_FILE.read_text(encoding="utf-8")


def _read_chat_layout() -> str:
    return CHAT_LAYOUT_FILE.read_text(encoding="utf-8")


def _read_chat_panel() -> str:
    return CHAT_PANEL_FILE.read_text(encoding="utf-8")


def _read_main() -> str:
    return MAIN_FILE.read_text(encoding="utf-8")


def _read_main_js() -> str:
    return MAIN_JS_FILE.read_text(encoding="utf-8")


def test_chat_page_uses_page_centric_workbench_layout():
    chat_layout = _read_chat_layout()
    chat_panel = _read_chat_panel()

    ask_panel_label = "right-ask-tabs"
    assert ask_panel_label in chat_layout
    assert 'elem_id="answer-expand"' in chat_layout
    assert 'with gr.Row(elem_id="page-workbench-layout"):' in chat_layout
    assert 'with gr.Column(elem_id="info-expand"):' in chat_layout
    assert "knowledge-map-title" not in chat_layout
    assert (
        "value=\"<div class='pdf-preview-notice'>Selected page preview.</div>\""
        in chat_panel
    )
    assert 'placeholder="Ask a question about the selected page"' in chat_panel
    assert "Vision Transformer (ViT)" not in chat_panel
    assert "Select a file and page to preview." in chat_panel

    assert chat_layout.index(
        "page.chat_panel.render_notice_and_pager()"
    ) < chat_layout.index("page.chat_panel.render_input()")
    assert chat_layout.index("_ask_tabs_html()") < chat_layout.index(
        "page.chat_panel.render_input()"
    )
    assert chat_layout.index("render_answer_panel(page") < chat_layout.index(
        "page.followup_questions = page.chat_suggestion.examples"
    )


def test_workbench_matches_reference_prototype_structure():
    chat_page = _read_chat_page()
    chat_layout = _read_chat_layout()
    chat_ui = f"{chat_page}\n{chat_layout}"
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
        assert token in chat_ui

    assert "render_preview_frame()" in chat_panel
    assert 'placeholder="Search files..."' in chat_layout
    assert "right-ask-tabs" in chat_layout
    assert 'label="Chat settings"' not in chat_ui
    assert "refresh_page_context_view" in chat_page
    assert "_render_page_thumbnail_strip" in chat_page
    assert "page.page_strip_search = gr.State" in chat_layout
    assert 'placeholder="Search within file..."' not in chat_ui
    assert "refresh_page_thumbnail_search" not in chat_ui
    assert "Suggested questions for this page" not in chat_ui
    assert "_render_text_thumbnail_preview" in chat_page
    assert chat_layout.index("_ask_tabs_html()") < chat_layout.index("info-expand")

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
    assert "data-reader-action='zoom-in'" in chat_layout
    assert "bindReaderToolbarControls" in main_js
    assert "--reader-preview-zoom" in main_js
    assert "page._render_reasoning_trace_html()" in chat_layout
    assert "page._render_citations_card_html()" in chat_layout
    assert "render_studio_trace_panel" in chat_page
    assert "response.artifact" in chat_page
    assert "render_conversation_notebook_root" in chat_page
    assert "render_latest_reasoning_trace" in chat_page
    assert "render_latest_citations_card" in chat_page
    assert "Citations (3)" not in chat_page
    assert "Patch embedding definition" not in chat_page
    assert "Steps 4" not in chat_page
    assert "Query rewrite" not in chat_page
    assert "Rerank" not in chat_page
