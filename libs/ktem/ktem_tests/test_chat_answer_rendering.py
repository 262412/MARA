from typing import cast

from ktem.pages.chat import ChatPage


def _chat_page() -> ChatPage:
    return cast(ChatPage, object.__new__(ChatPage))


def test_assistant_answer_panel_renders_markdown_tables():
    content = (
        "| Component | Input | Output |\n"
        "| :--- | :--- | :--- |\n"
        "| Encoder | Input Embeddings | Contextual representation |\n"
    )

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "<table>" in html
    assert "<th" in html
    assert ">Component</th>" in html
    assert "| Component |" not in html


def test_assistant_answer_panel_preserves_latex_delimiters():
    content = "The update is $w_{n+1} = w_n - \\eta \\nabla L(w_n)$."

    html = _chat_page()._format_chat_message(content, "assistant")

    assert "$w_{n+1} = w_n - \\eta \\nabla L(w_n)$" in html


def test_user_answer_panel_escapes_html_without_markdown_rendering():
    content = "<script>alert('x')</script>\n| not | a table |"

    html = _chat_page()._format_chat_message(content, "user")

    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert "<table>" not in html
