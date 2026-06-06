from typing import cast

from ktem.pages.chat import ChatPage


def _chat_page() -> ChatPage:
    return cast(ChatPage, object.__new__(ChatPage))


def test_assistant_answer_panel_renders_markdown_tables():
    content = (
        "Summary:\n"
        "| Component | Input | Output |\n"
        "| :--- | :--- | :--- |\n"
        "| Encoder | Input Embeddings | Contextual representation |\n"
    )

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "<table>" in html
    assert "<th" in html
    assert ">Component</th>" in html
    assert "| Component |" not in html


def test_assistant_answer_panel_treats_br_tags_as_line_breaks():
    content = "Summary:<br>| Metric | Value |<br>|---|---|<br>| Loss | $L(w)$ |"

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "<table>" in html
    assert ">Metric</th>" in html
    assert "&lt;br&gt;" not in html
    assert "<br>| Metric |" not in html


def test_assistant_answer_panel_marks_inline_latex_for_katex_rendering():
    content = "The update is $w_{n+1} = w_n - \\eta \\nabla L(w_n)$."

    html = _chat_page()._format_chat_message(content, "assistant")

    assert 'class="ktem-math-source"' in html
    assert 'data-ktem-display="false"' in html
    assert "w_{n+1} = w_n - \\eta \\nabla L(w_n)" in html


def test_assistant_answer_panel_marks_display_latex_for_katex_rendering():
    content = "Formula:\n$$\nE = mc^2\n$$"

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "ktem-math-source--display" in html
    assert 'data-ktem-display="true"' in html
    assert "E = mc^2" in html


def test_assistant_answer_panel_normalizes_multiline_display_latex():
    content = "Formula:\n$$\na=b\nc=d\n$$"

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "\\begin{aligned}" in html
    assert "a &amp;= b" in html
    assert "c &amp;= d" in html


def test_user_answer_panel_escapes_html_without_markdown_rendering():
    content = "<script>alert('x')</script>\n| not | a table |"

    html = _chat_page()._format_chat_message(content, "user")

    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert "<table>" not in html
