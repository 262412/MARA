from __future__ import annotations

import re

from docx.oxml.ns import qn

from .docx_relationships import DOCX_NAMESPACES, DocxRelationshipResolver
from .docx_security import DocxHtmlBudget, escape, escaped_html_length, safe_font

IMAGE_MARKUP_CHARS = len('<img class="docx-image" src="') + len(
    '" alt="" loading="lazy"/>'
)
IMAGE_ALT_MARKUP_CHARS = len("<span class='docx-image-alt'></span>")
HYPERLINK_MARKUP_CHARS = len(
    '<a href="" target="_blank" rel="noopener noreferrer"></a>'
)


class DocxRunRenderer:
    def __init__(
        self,
        relationships: DocxRelationshipResolver,
        base_font_name: str,
        html_budget: DocxHtmlBudget,
    ) -> None:
        self._relationships = relationships
        self._base_font_name = base_font_name
        self._html_budget = html_budget

    def render_run(self, run_element) -> str:
        style_tokens, bold, italic, underline = self._run_style(run_element)
        style_attr = f' style="{"".join(style_tokens)}"' if style_tokens else ""
        wrapper_chars = len("<span></span>") + len(style_attr)
        wrapper_chars += len("<strong></strong>") if bold else 0
        wrapper_chars += len("<em></em>") if italic else 0
        wrapper_chars += len("<u></u>") if underline else 0
        checkpoint = self._html_budget.checkpoint()
        self._html_budget.reserve(wrapper_chars)
        content = self._render_run_content(run_element)
        if not content:
            self._html_budget.restore(checkpoint)
            return ""
        if bold:
            content = f"<strong>{content}</strong>"
        if italic:
            content = f"<em>{content}</em>"
        if underline:
            content = f"<u>{content}</u>"
        return f"<span{style_attr}>{content}</span>"

    def render_hyperlink(self, hyperlink_element) -> str:
        parts = [
            rendered
            for run in hyperlink_element.findall("w:r", DOCX_NAMESPACES)
            if (rendered := self.render_run(run))
        ]
        inner = "".join(parts).strip()
        if not inner:
            return ""
        target = self._relationships.hyperlink_target(hyperlink_element)
        if not target:
            return inner
        escaped_target_length = escaped_html_length(target)
        if not self._html_budget.try_reserve(
            HYPERLINK_MARKUP_CHARS + escaped_target_length
        ):
            return inner
        return (
            f'<a href="{escape(target)}" target="_blank" '
            f'rel="noopener noreferrer">{inner}</a>'
        )

    def _render_run_content(self, run_element) -> str:
        parts: list[str] = []
        for node in run_element:
            name = _local_name(node.tag)
            if name == "t" and node.text:
                self._html_budget.reserve(escaped_html_length(node.text))
                parts.append(escape(node.text))
            elif name in {"br", "cr"}:
                rendered = self._render_break(node, name)
                self._html_budget.reserve(len(rendered))
                parts.append(rendered)
            elif name == "tab":
                self._html_budget.reserve(len("&emsp;"))
                parts.append("&emsp;")
            elif name == "drawing":
                rendered = self._render_image(node)
                if rendered:
                    parts.append(rendered)
        return "".join(parts)

    @staticmethod
    def _render_break(node, name: str) -> str:
        if name == "br":
            break_type = (node.attrib.get(qn("w:type"), "") or "").strip().lower()
            if break_type == "page":
                return "<span class='docx-page-break'></span>"
        return "<br/>"

    def _render_image(self, drawing_element) -> str:
        image = self._relationships.embedded_image(
            drawing_element,
            markup_chars=IMAGE_MARKUP_CHARS,
        )
        if image.data_url:
            alt_text = escape(image.alt_text)
            return (
                f'<img class="docx-image" src="{image.data_url}" '
                f'alt="{alt_text}" loading="lazy"/>'
            )
        if image.alt_text:
            self._html_budget.reserve(
                IMAGE_ALT_MARKUP_CHARS + escaped_html_length(image.alt_text)
            )
            alt_text = escape(image.alt_text)
            return f"<span class='docx-image-alt'>{alt_text}</span>"
        return ""

    def _run_style(self, run_element) -> tuple[list[str], bool, bool, bool]:
        properties = run_element.find("w:rPr", DOCX_NAMESPACES)
        if properties is None:
            return [], False, False, False
        tokens: list[str] = []
        color = properties.find("w:color", DOCX_NAMESPACES)
        color_value = color.attrib.get(qn("w:val"), "") if color is not None else ""
        if re.fullmatch(r"[0-9A-Fa-f]{6}", color_value or ""):
            tokens.append(f"color:#{color_value};")
        size = properties.find("w:sz", DOCX_NAMESPACES)
        size_value = size.attrib.get(qn("w:val"), "") if size is not None else ""
        try:
            points = max(8.0, min(20.0, int(size_value) / 2.0))
            tokens.append(f"font-size:{max(0.82, min(1.35, points / 12.0)):.2f}em;")
        except (TypeError, ValueError):
            pass
        fonts = properties.find("w:rFonts", DOCX_NAMESPACES)
        if fonts is not None:
            requested = (
                fonts.attrib.get(qn("w:ascii"), "")
                or fonts.attrib.get(qn("w:hAnsi"), "")
                or ""
            )
            font_name = safe_font(requested, self._base_font_name)
            tokens.append(
                f"font-family:'{escape(font_name)}',"
                f"'{escape(self._base_font_name)}',serif;"
            )
        return (
            tokens,
            properties.find("w:b", DOCX_NAMESPACES) is not None,
            properties.find("w:i", DOCX_NAMESPACES) is not None,
            properties.find("w:u", DOCX_NAMESPACES) is not None,
        )


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag
