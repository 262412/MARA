from __future__ import annotations

from dataclasses import dataclass

from docx.oxml.ns import qn

from .docx_relationships import DOCX_NAMESPACES
from .docx_runs import DocxRunRenderer, _local_name
from .docx_security import DocxHtmlBudget, escape, escaped_html_length


@dataclass(frozen=True)
class ParagraphMarkup:
    tag: str
    style_attr: str
    inner_html: str
    list_tag: str | None
    list_level: int


class DocxNumbering:
    def __init__(
        self,
        number_to_abstract: dict[str, str],
        abstract_formats: dict[tuple[str, int], str],
    ) -> None:
        self._number_to_abstract = number_to_abstract
        self._abstract_formats = abstract_formats

    @classmethod
    def from_document(cls, document) -> DocxNumbering:
        number_to_abstract: dict[str, str] = {}
        abstract_formats: dict[tuple[str, int], str] = {}
        try:
            root = document.part.numbering_part.element
        except (AttributeError, KeyError, NotImplementedError):
            return cls(number_to_abstract, abstract_formats)
        for number in root.findall(".//w:num", DOCX_NAMESPACES):
            number_id = number.attrib.get(qn("w:numId"), "")
            abstract = number.find("w:abstractNumId", DOCX_NAMESPACES)
            abstract_id = (
                abstract.attrib.get(qn("w:val"), "") if abstract is not None else ""
            )
            if number_id and abstract_id:
                number_to_abstract[number_id] = abstract_id
        for abstract in root.findall(".//w:abstractNum", DOCX_NAMESPACES):
            abstract_id = abstract.attrib.get(qn("w:abstractNumId"), "")
            for level in abstract.findall("w:lvl", DOCX_NAMESPACES):
                level_id = level.attrib.get(qn("w:ilvl"), "0")
                number_format = level.find("w:numFmt", DOCX_NAMESPACES)
                format_value = (
                    number_format.attrib.get(qn("w:val"), "")
                    if number_format is not None
                    else ""
                )
                try:
                    abstract_formats[
                        (abstract_id, int(level_id))
                    ] = format_value.lower()
                except (TypeError, ValueError):
                    continue
        return cls(number_to_abstract, abstract_formats)

    def format_for(self, number_id: str, level: int) -> str:
        abstract_id = self._number_to_abstract.get(number_id, "")
        return self._abstract_formats.get((abstract_id, level), "")


class DocxParagraphRenderer:
    def __init__(
        self,
        runs: DocxRunRenderer,
        numbering: DocxNumbering,
        html_budget: DocxHtmlBudget,
    ) -> None:
        self._runs = runs
        self._numbering = numbering
        self._html_budget = html_budget

    def render(self, paragraph) -> ParagraphMarkup | None:
        text = paragraph.text or ""
        has_image = paragraph._p.find(".//a:blip", DOCX_NAMESPACES) is not None
        if not text.strip() and not has_image:
            return None
        inner_parts: list[str] = []
        for child in paragraph._p:
            child_name = _local_name(child.tag)
            rendered = ""
            if child_name == "r":
                rendered = self._runs.render_run(child)
            elif child_name == "hyperlink":
                rendered = self._runs.render_hyperlink(child)
            if rendered:
                inner_parts.append(rendered)
        if inner_parts:
            inner_html = "".join(inner_parts)
        else:
            self._html_budget.reserve(escaped_html_length(text))
            inner_html = escape(text)
        style_name = _style_name(paragraph)
        tag = _paragraph_tag(style_name)
        list_tag, list_level = self._list_info(paragraph, style_name)
        style_tokens = self._paragraph_style(paragraph, is_list=bool(list_tag))
        style_attr = f' style="{"".join(style_tokens)}"' if style_tokens else ""
        return ParagraphMarkup(tag, style_attr, inner_html, list_tag, list_level)

    @staticmethod
    def _paragraph_style(paragraph, *, is_list: bool) -> list[str]:
        tokens: list[str] = []
        paragraph_format = paragraph.paragraph_format
        try:
            left_indent = paragraph_format.left_indent
            if left_indent and left_indent.pt:
                tokens.append(f"padding-left:{max(0, int(left_indent.pt))}pt;")
        except (AttributeError, TypeError, ValueError):
            pass
        try:
            first_indent = paragraph_format.first_line_indent
            if not is_list and first_indent and first_indent.pt and first_indent.pt > 0:
                tokens.append(f"text-indent:{int(first_indent.pt)}pt;")
        except (AttributeError, TypeError, ValueError):
            pass
        alignment = paragraph.alignment
        if alignment is None and paragraph.style:
            alignment = paragraph.style.paragraph_format.alignment
        if alignment is not None:
            aligned = {0: "left", 1: "center", 2: "right", 3: "justify"}.get(
                int(alignment)
            )
            if aligned:
                tokens.append(f"text-align:{aligned};")
        return tokens

    def _list_info(self, paragraph, style_name: str) -> tuple[str | None, int]:
        properties = paragraph._p.pPr
        numbering = properties.numPr if properties is not None else None
        level = 0
        number_id = ""
        try:
            if numbering is not None and numbering.ilvl is not None:
                level = int(numbering.ilvl.val)
            if numbering is not None and numbering.numId is not None:
                number_id = str(numbering.numId.val)
        except (AttributeError, TypeError, ValueError):
            level = 0
            number_id = ""
        if number_id:
            number_format = self._numbering.format_for(number_id, level)
            if number_format == "bullet":
                return "ul", level
            if number_format:
                return "ol", level
        if "list bullet" in style_name or "bullet" in style_name:
            return "ul", level
        if "list number" in style_name or "number" in style_name:
            return "ol", level
        if numbering is not None:
            return "ul", level
        return None, 0


class DocxTableRenderer:
    def __init__(
        self,
        paragraphs: DocxParagraphRenderer,
        html_budget: DocxHtmlBudget,
    ) -> None:
        self._paragraphs = paragraphs
        self._html_budget = html_budget

    def render(self, table) -> str:
        self._html_budget.reserve(len("<table><tbody></tbody></table>"))
        rows: list[str] = []
        for row in table.rows:
            self._html_budget.reserve(len("<tr></tr>"))
            cells: list[str] = []
            for cell in row.cells:
                self._html_budget.reserve(len("<td></td>"))
                cells.append(f"<td>{self._render_cell(cell)}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return f"<table><tbody>{''.join(rows)}</tbody></table>"

    def _render_cell(self, cell) -> str:
        parts: list[str] = []
        for paragraph in cell.paragraphs:
            markup = self._paragraphs.render(paragraph)
            if markup is None:
                continue
            tag = markup.tag if markup.list_tag is None else "p"
            self._html_budget.reserve(len(f"<{tag}{markup.style_attr}></{tag}>"))
            parts.append(f"<{tag}{markup.style_attr}>{markup.inner_html}</{tag}>")
        return "".join(parts)


def _style_name(paragraph) -> str:
    if not paragraph.style:
        return ""
    return str(paragraph.style.name or "").lower()


def _paragraph_tag(style_name: str) -> str:
    if "heading 1" in style_name or style_name == "title":
        return "h1"
    if "heading 2" in style_name:
        return "h2"
    if "heading 3" in style_name:
        return "h3"
    return "p"
