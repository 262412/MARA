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


def test_assistant_answer_panel_wraps_tables_in_horizontal_scroll_region():
    content = (
        "| Item | Summary |\n"
        "| --- | --- |\n"
        "| Self-RAG-style controller | "
        "A program component that dynamically selects the answer route. |\n"
    )

    html = _chat_page()._format_chat_message(content, "assistant")

    assert 'class="ktem-answer-table-scroll"' in html
    assert 'role="region"' in html
    assert 'aria-label="Scrollable table"' in html
    assert 'tabindex="0"' in html
    assert html.index('class="ktem-answer-table-scroll"') < html.index("<table>")


def test_assistant_answer_panel_wraps_chart_images_in_horizontal_scroll_region():
    content = "![Route comparison chart](route-comparison.png)"

    html = _chat_page()._format_chat_message(content, "assistant")

    assert 'class="ktem-answer-chart-scroll"' in html
    assert 'role="region"' in html
    assert 'aria-label="Scrollable chart"' in html
    assert 'tabindex="0"' in html
    assert html.index('class="ktem-answer-chart-scroll"') < html.index("<img")


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


def test_assistant_answer_panel_breaks_inline_bold_sections_into_paragraphs():
    content = (
        "Based on the provided context, the slide introduces transformers. "
        "**What is a Transformer:** A deep learning architecture based on attention. "
        "**Part 1 - Attention:** Each token constructs Query, Key, and Value vectors."
    )

    html = _chat_page()._format_chat_message(content, "assistant")

    assert html.count("<p>") >= 3
    assert "<strong>What is a Transformer:</strong>" in html
    assert "<strong>Part 1 - Attention:</strong>" in html


def test_assistant_answer_panel_converts_inline_pipe_pairs_to_table():
    content = (
        'This slide is titled "Deep Dive to Attention". '
        "| What it is | Scaled dot-product attention computes attention weights. "
        "| Formula | $A = \\operatorname{softmax}(QK^T / \\sqrt{d_k})V$. "
        "| Multi-head extension | Multiple $Q, K, V$ sets are computed in parallel."
    )

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "<table>" in html
    assert ">Item</th>" in html
    assert ">Summary</th>" in html
    assert "<td>Formula</td>" in html
    assert 'data-ktem-latex="A = \\operatorname{softmax}(QK^T / \\sqrt{d_k})V"' in html
    assert "| What it is |" not in html


def test_user_answer_panel_escapes_html_without_markdown_rendering():
    content = "<script>alert('x')</script>\n| not | a table |"

    html = _chat_page()._format_chat_message(content, "user")

    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert "<table>" not in html
