from types import SimpleNamespace
from typing import Any, cast

from ktem.pages.chat import ChatPage


def test_page_thumbnail_strip_renders_all_pages():
    page = ChatPage.__new__(ChatPage)
    page.page_preview = cast(
        Any,
        SimpleNamespace(_get_page_preview_image=lambda *_args: ""),
    )

    rendered = page._render_page_thumbnail_strip(
        "pdf-1", "paper.pdf", "paper.pdf", 1, 18
    )

    assert rendered.count("data-page-number=") == 18
    assert "data-page-number='18'" in rendered


def test_chat_file_list_keeps_collection_scope_when_file_is_selected():
    page = cast(Any, ChatPage.__new__(ChatPage))
    captured = {}
    rows = [
        {"id": "pdf-1", "name": "Paper.pdf"},
        {"id": "doc-1", "name": "Notes.docx"},
    ]

    def _source_rows_for_sidebar(
        user_id, first_selector_choices, scoped_ids, conversation_id, keyword
    ):
        captured["scoped_ids"] = scoped_ids
        return (
            rows if not scoped_ids else [row for row in rows if row["id"] in scoped_ids]
        )

    page._source_rows_for_sidebar = _source_rows_for_sidebar
    page._render_chat_file_list_html = lambda next_rows, selected: (
        ",".join(row["id"] for row in next_rows)
    )
    page._render_corpus_summary_html = lambda next_rows: str(len(next_rows))

    rendered_rows, list_html, selected_label, summary = page.refresh_chat_file_list(
        "",
        "user",
        [],
        ["pdf-1"],
        ["pdf-1"],
        "",
    )

    assert captured["scoped_ids"] == []
    assert rendered_rows == rows
    assert list_html == "pdf-1,doc-1"
    assert selected_label == "Focus: Paper.pdf"
    assert summary == "2"


def test_chat_file_list_highlights_selected_file_without_hiding_others():
    page = ChatPage.__new__(ChatPage)
    rows = [
        {"id": "pdf-1", "name": "Paper.pdf", "page_count": 3, "size": 1000},
        {"id": "doc-1", "name": "Notes.docx", "page_count": 2, "size": 2000},
    ]

    html = page._render_chat_file_list_html(rows, {"pdf-1"})

    assert "data-chat-file-id='pdf-1'" in html
    assert "data-chat-file-id='doc-1'" in html
    assert html.count("is-selected") == 1
    assert "Paper.pdf" in html
    assert "Notes.docx" in html


def test_reader_toolbar_exposes_only_implemented_actions():
    source = ChatPage.__module__
    assert source == "ktem.pages.chat"

    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    chat_page = (package_root / "pages" / "chat" / "__init__.py").read_text(
        encoding="utf-8"
    )
    main_js = (package_root / "assets" / "js" / "main.js").read_text(encoding="utf-8")

    for action in ["pan", "select", "area", "annotate"]:
        assert f"data-reader-action='{action}'" not in chat_page
    assert "setReaderMode" not in main_js
    assert "data-reader-action='zoom-in'" in chat_page
    assert "data-reader-action='download'" in chat_page


def test_ask_page_panel_is_not_a_collapsible_accordion():
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    chat_page = (package_root / "pages" / "chat" / "__init__.py").read_text(
        encoding="utf-8"
    )
    css = (package_root / "assets" / "css" / "main.css").read_text(encoding="utf-8")

    assert 'gr.Accordion(\n                    label="Ask This Page"' not in chat_page
    assert 'with gr.Column(elem_id="answer-expand")' in chat_page
    assert "Suggested questions for this page" not in chat_page
    assert 'elem_id="suggested-question-list"' not in chat_page
    assert (
        "#info-expand-button {\n  position: static;\n  display: none !important;" in css
    )


def test_workbench_removes_static_search_and_accordion_controls():
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    chat_page = (package_root / "pages" / "chat" / "__init__.py").read_text(
        encoding="utf-8"
    )
    chat_control = (package_root / "pages" / "chat" / "control.py").read_text(
        encoding="utf-8"
    )
    main_js = (package_root / "assets" / "js" / "main.js").read_text(encoding="utf-8")
    pdf_viewer_js = (package_root / "assets" / "js" / "pdf_viewer.js").read_text(
        encoding="utf-8"
    )

    assert 'placeholder="Search within file..."' not in chat_page
    assert 'self.page_strip_search = gr.State(value="")' in chat_page
    assert 'label="Knowledge Map (Page-level)"' not in chat_page
    assert "Knowledge Map (Page-level)" not in chat_page
    assert 'elem_id="knowledge-graph-refresh"' not in chat_page
    assert 'elem_id="knowledge-graph-status"' not in chat_page
    assert 'id="pdf-modal"' not in chat_page
    assert 'elem_id="info-expand-button"' not in chat_control
    assert "self.knowledge_graph_refresh = gr.Button" not in chat_page
    assert 'elem_id="knowledge-graph-plot"' not in chat_page
    assert 'self.plot_panel = gr.HTML("", visible=False)' in chat_page
    assert 'document.querySelector("#knowledge-graph-plot")' not in main_js
    assert 'document.querySelectorAll(".knowledge-graph-shell")' in main_js
    assert 'with gr.Column(elem_id="info-expand"):' in chat_page
    assert 'modal = document.createElement("div")' in pdf_viewer_js
    assert "document.body.appendChild(modal)" in pdf_viewer_js
    assert "corpusAddPanel.classList.toggle" not in main_js
    assert "fileInput.click()" in main_js


def test_workbench_css_keeps_long_lists_inside_scrollable_columns():
    import re
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    css = (package_root / "assets" / "css" / "main.css").read_text(encoding="utf-8")

    assert "#page-workbench-layout {" in css
    assert "#reader-workbench {" in css
    assert "display: grid !important;" in css
    assert "#page-workbench-layout::before" in css
    assert "#reader-workbench::before" in css
    assert "calc(100% - var(--workbench-right-width))" in css
    assert "left: var(--page-rail-width);" in css
    assert (
        "#chat-tab {\n  min-height: var(--workbench-viewport-height) !important;" in css
    )
    assert "height: auto !important;" in css
    assert "overflow-y: auto !important;" in css
    assert "#chat-file-list {\n  flex: 1 1 auto !important;" in css
    assert "#page-thumbnail-list {\n  flex: 1 1 auto !important;" in css
    assert "#workbench-file-summary {\n  flex: 0 0 auto !important;" in css
    assert (
        "#chat-info-panel {\n  flex: 0 0 var(--workbench-right-width) !important;"
        in css
    )
    for selector in [
        "#conv-settings-panel",
        "#page-strip-panel",
        "#chat-info-panel",
    ]:
        blocks = [
            css[match.start() : css.index("}", match.start())]
            for match in re.finditer(rf"^{re.escape(selector)} \{{", css, flags=re.M)
        ]
        assert any(
            "height: var(--workbench-viewport-height) !important;" in block
            for block in blocks
        )
        assert any("position: sticky !important;" in block for block in blocks)
        assert any("top: 0 !important;" in block for block in blocks)
    for selector in ["#chat-area", "#document-reader-panel"]:
        blocks = [
            css[match.start() : css.index("}", match.start())]
            for match in re.finditer(rf"^{re.escape(selector)} \{{", css, flags=re.M)
        ]
        assert any("height: auto !important;" in block for block in blocks)
        assert any("overflow: visible !important;" in block for block in blocks)
    chat_info_blocks = [
        css[match.start() : css.index("}", match.start())]
        for match in re.finditer(r"^#chat-info-panel \{", css, flags=re.M)
    ]
    assert any("flex-wrap: nowrap !important;" in block for block in chat_info_blocks)
    assert "overflow-y: auto !important;" in css[css.index("#chat-file-list {") :]
    assert "overflow-y: auto !important;" in css[css.index("#page-thumbnail-list {") :]


def test_answer_panel_renders_rich_markdown_and_math():
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    css = (package_root / "assets" / "css" / "main.css").read_text(encoding="utf-8")
    main_js = (package_root / "assets" / "js" / "main.js").read_text(encoding="utf-8")

    assert "function enforceAnswerPanelScroll()" in main_js
    assert 'const infoPanel = document.getElementById("chat-info-panel")' in main_js
    assert "answerPanel.style.maxHeight =" in main_js
    assert 'answerPanel.style.overflowY = "auto";' in main_js
    assert 'window.addEventListener("resize", enforceAnswerPanelScroll);' in main_js
    assert "renderAnswerPanelMath" in main_js
    assert "katex.renderToString" in main_js
    assert ".ktem-math-source" in main_js
    assert 'self.answer_panel = gr.HTML(value="", elem_id="answer-panel")' in (
        package_root / "pages" / "chat" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "#html-info-panel,\n#answer-panel {\n  height: 100% !important;" not in css
    for token in [
        "#answer-panel .chat-message-content p",
        "#answer-panel .chat-message-content ul",
        "#answer-panel .chat-message-content table",
        "#answer-panel .chat-message-content th",
        "#answer-panel .chat-message-content pre",
        "#answer-panel .ktem-math--display",
        "--answer-panel-max-height:",
        "max-height: var(--answer-panel-max-height);",
        "overflow-y: auto !important;",
        "max-width: none;",
        "margin: 12px 8px;",
        "overflow-wrap: anywhere;",
    ]:
        assert token in css
