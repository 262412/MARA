from __future__ import annotations

import re

from docx.oxml.ns import qn

from .docx_relationships import DOCX_NAMESPACES, DocxRelationshipResolver
from .docx_security import escape, safe_font


class DocxRunRenderer:
    def __init__(
        self,
        relationships: DocxRelationshipResolver,
        base_font_name: str,
    ) -> None:
        self._relationships = relationships
        self._base_font_name = base_font_name

    def render_run(self, run_element) -> str:
        content = self._render_run_content(run_element)
        if not content:
            return ""
        style_tokens, bold, italic, underline = self._run_style(run_element)
        if bold:
            content = f"<strong>{content}</strong>"
        if italic:
            content = f"<em>{content}</em>"
        if underline:
            content = f"<u>{content}</u>"
        style_attr = f' style="{"".join(style_tokens)}"' if style_tokens else ""
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
        return (
            f'<a href="{escape(target)}" target="_blank" '
            f'rel="noopener noreferrer">{inner}</a>'
        )

    def _render_run_content(self, run_element) -> str:
        parts: list[str] = []
        for node in run_element:
            name = _local_name(node.tag)
            if name == "t" and node.text:
                parts.append(escape(node.text))
            elif name in {"br", "cr"}:
                parts.append(self._render_break(node, name))
            elif name == "tab":
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
        image = self._relationships.embedded_image(drawing_element)
        alt_text = escape(image.alt_text)
        if image.data_url:
            return (
                f'<img class="docx-image" src="{image.data_url}" '
                f'alt="{alt_text}" loading="lazy"/>'
            )
        if alt_text:
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
