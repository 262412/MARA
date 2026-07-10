from html.parser import HTMLParser
from types import SimpleNamespace
from typing import cast
from urllib.parse import urlsplit

from ktem.pages.chat.answer_rendering import format_chat_message_html
from ktem.reasoning.simple import FullQAPipeline
from ktem.utils.render import Render

from kotaemon.base import RetrievedDocument

HOSTILE_HTML = (
    '<img src="x" onerror="globalThis.__maraXss += 1">'
    "<script>globalThis.__maraXss += 10</script>"
    '<a href="javascript:globalThis.__maraXss += 100">script URL</a>'
    '<a href="data:text/html,<script>globalThis.__maraXss += 1000</script>">'
    "data URL</a></summary></details>"
)


class _ActiveContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self.active.append("script")
        for name, value in attrs:
            lowered_name = name.lower()
            lowered_value = str(value or "").strip().lower()
            if lowered_name.startswith("on"):
                self.active.append(lowered_name)
            if lowered_name in {"href", "src", "xlink:href"}:
                scheme = urlsplit(lowered_value).scheme
                if scheme == "javascript" or lowered_value.startswith("data:text/html"):
                    self.active.append(f"{lowered_name}={scheme or 'data'}")


def _assert_hostile_markup_is_inert(rendered: str) -> None:
    parser = _ActiveContentParser()
    parser.feed(rendered)
    assert parser.active == []


def test_evidence_markdown_strips_active_content_and_unsafe_urls():
    rendered = Render.table(f"# Evidence\n\n{HOSTILE_HTML}")

    _assert_hostile_markup_is_inert(rendered)
    assert "Evidence" in rendered
    assert "script URL" in rendered
    assert "data URL" in rendered


def test_collapsible_sanitizes_planner_header_and_content():
    rendered = Render.collapsible(
        header=f"Planner {HOSTILE_HTML}",
        content=f"<p>Step output</p>{HOSTILE_HTML}",
        open=True,
    )

    _assert_hostile_markup_is_inert(rendered)
    assert "<details" in rendered
    assert "<summary>" in rendered
    assert "Planner" in rendered
    assert "Step output" in rendered


def test_document_metadata_preview_and_body_are_sanitized(tmp_path):
    pdf_path = tmp_path / 'report" onmouseover="globalThis.__maraXss=1.pdf'
    pdf_path.write_bytes(b"%PDF-1.4\n")
    doc = RetrievedDocument(
        text=f"Evidence body {HOSTILE_HTML}",
        score=0.5,
        metadata={
            "file_name": f"quarterly {HOSTILE_HTML}.pdf",
            "file_path": str(pdf_path),
            "file_type": "application/pdf",
            "page_label": 7,
            "reranking_score": 0.8,
        },
    )

    rendered = Render.collapsible_with_header_score(
        doc,
        highlight_text=f"selected {HOSTILE_HTML}",
        open_collapsible=True,
    )

    _assert_hostile_markup_is_inert(rendered)
    assert 'class="pdf-link"' in rendered or "class='pdf-link'" in rendered
    assert 'data-page="7"' in rendered or "data-page='7'" in rendered
    assert "Evidence body" in rendered
    assert "quarterly" in rendered


def test_image_and_highlight_render_document_fields_as_inert_text():
    image = Render.image("javascript:globalThis.__maraXss=1", HOSTILE_HTML)
    highlight = Render.highlight(HOSTILE_HTML, "x' onmouseover='globalThis.__maraXss=1")

    _assert_hostile_markup_is_inert(image)
    _assert_hostile_markup_is_inert(highlight)
    assert "<mark" in highlight
    assert "script URL" in image


def test_safe_evidence_structure_survives_the_allowlist():
    markdown = (
        "> Quoted evidence\n\n"
        "| Metric | Value |\n"
        "| --- | --- |\n"
        "| Revenue | 42 |\n\n"
        "```python\nprint('safe')\n```\n\n"
        "<mark id='mark-citation-1'>cited phrase</mark>"
    )

    rendered = Render.table(markdown)

    assert "<blockquote>" in rendered
    assert "<table>" in rendered
    assert "<pre>" in rendered and "<code" in rendered
    assert "<mark" in rendered
    assert "mark-citation-1" in rendered

    citation = Render.table("<a href='#' class='citation' id='mark-2'>【2】</a>")
    assert 'class="citation"' in citation
    assert 'id="mark-2"' in citation


def test_mindmap_template_escapes_model_controlled_closing_tags():
    mindmap_text = (
        "# Root\n## Safe node\n</script><img src=x onerror='globalThis.__xss=1'>"
    )
    answer = SimpleNamespace(metadata={"mindmap": SimpleNamespace(text=mindmap_text)})

    pipeline = cast(FullQAPipeline, object())
    rendered = FullQAPipeline.prepare_mindmap(pipeline, answer)

    assert rendered is not None
    assert '<script type="text/template">' in rendered.content
    assert "# Root" in rendered.content
    assert "## Safe node" in rendered.content
    assert "</script><img" not in rendered.content
    assert "&lt;/script&gt;&lt;img" in rendered.content


def test_answer_rendering_keeps_hostile_markdown_as_text():
    rendered = format_chat_message_html(HOSTILE_HTML, "assistant")

    _assert_hostile_markup_is_inert(rendered)
    assert "&lt;img" in rendered


def test_answer_markdown_rejects_unsafe_link_and_image_urls():
    content = (
        "[script link](javascript:globalThis.__maraXss=1)\n\n"
        "![script image](javascript:globalThis.__maraXss=2)\n\n"
        "[data link](data:text/html,<script>globalThis.__maraXss=3</script>)"
    )

    rendered = format_chat_message_html(content, "assistant")

    _assert_hostile_markup_is_inert(rendered)
    assert "script link" in rendered
    assert "script image" in rendered
    assert "data link" in rendered
