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
        [],
        "",
    )

    assert captured["scoped_ids"] == []
    assert rendered_rows == rows
    assert list_html == "pdf-1,doc-1"
    assert selected_label == "Focus: Paper.pdf"
    assert summary == "2"


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
    assert (
        "#info-expand-button {\n  position: static;\n  display: none !important;" in css
    )


def test_workbench_css_uses_page_scroll_and_full_height_dividers():
    import re
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1] / "ktem"
    css = (package_root / "assets" / "css" / "main.css").read_text(encoding="utf-8")

    assert "#page-workbench-layout {\n  display: grid !important;" in css
    assert "#reader-workbench {\n  display: grid !important;" in css
    assert "padding-bottom: var(--mara-statusbar-height) !important;" in css
    for selector in [
        "#conv-settings-panel",
        "#chat-area",
        "#page-strip-panel",
        "#document-reader-panel",
        "#chat-info-panel",
    ]:
        blocks = [
            css[match.start() : css.index("}", match.start())]
            for match in re.finditer(rf"^{re.escape(selector)} \{{", css, flags=re.M)
        ]
        assert any("max-height: none !important;" in block for block in blocks)
        assert any("overflow: visible !important;" in block for block in blocks)
