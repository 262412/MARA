from __future__ import annotations

from collections.abc import Iterator

from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from .docx_blocks import (
    DocxNumbering,
    DocxParagraphRenderer,
    DocxTableRenderer,
    ParagraphMarkup,
)
from .docx_relationships import DocxRelationshipResolver
from .docx_runs import DocxRunRenderer
from .docx_security import (
    DocxHtmlBudget,
    DocxHtmlBudgetExceeded,
    DocxImageBudget,
    escape,
    safe_font,
)


class DocxHtmlRenderer:
    def __init__(self, document) -> None:
        self._document = document
        self._base_font_name, self._base_font_size_em = _base_font(document)
        self._html_budget = DocxHtmlBudget()
        self._image_budget = DocxImageBudget()
        relationships = DocxRelationshipResolver(
            document.part.rels,
            self._image_budget,
            self._html_budget,
        )
        runs = DocxRunRenderer(
            relationships,
            self._base_font_name,
            self._html_budget,
        )
        paragraphs = DocxParagraphRenderer(
            runs,
            DocxNumbering.from_document(document),
            self._html_budget,
        )
        self._paragraphs = paragraphs
        self._tables = DocxTableRenderer(paragraphs, self._html_budget)

    def render(self, max_chars: int = 12000) -> str:
        self._html_budget.restore(0)
        self._image_budget.restore((0, 0))
        opening_tag = self._opening_tag()
        self._html_budget.reserve(len(opening_tag) + len("</div>"))
        parts = [opening_tag]
        active_lists: list[str] = []
        consumed = 0
        for block in _iter_blocks(self._document):
            if isinstance(block, Paragraph):
                block_chars = len(block.text or "")
                if consumed + block_chars > max_chars:
                    break
                if not self._render_paragraph_block(parts, active_lists, block):
                    break
                consumed += block_chars
                continue
            block_chars = _table_text_length(block)
            if consumed + block_chars > max_chars:
                break
            if not self._render_table_block(parts, active_lists, block):
                break
            consumed += block_chars
        self._close_lists(parts, active_lists)
        parts.append("</div>")
        return "".join(parts)

    def _render_paragraph_block(
        self,
        parts: list[str],
        active_lists: list[str],
        paragraph: Paragraph,
    ) -> bool:
        checkpoint = self._block_checkpoint(parts, active_lists)
        try:
            markup = self._paragraphs.render(paragraph)
            if markup is not None:
                self._append_paragraph(parts, active_lists, markup)
            return True
        except DocxHtmlBudgetExceeded:
            self._restore_block(parts, active_lists, checkpoint)
            return False

    def _render_table_block(
        self,
        parts: list[str],
        active_lists: list[str],
        table: Table,
    ) -> bool:
        checkpoint = self._block_checkpoint(parts, active_lists)
        try:
            self._close_lists(parts, active_lists)
            parts.append(self._tables.render(table))
            return True
        except DocxHtmlBudgetExceeded:
            self._restore_block(parts, active_lists, checkpoint)
            return False

    def _block_checkpoint(
        self,
        parts: list[str],
        active_lists: list[str],
    ) -> tuple[int, list[str], int, tuple[int, int]]:
        return (
            len(parts),
            list(active_lists),
            self._html_budget.checkpoint(),
            self._image_budget.checkpoint(),
        )

    def _restore_block(
        self,
        parts: list[str],
        active_lists: list[str],
        checkpoint: tuple[int, list[str], int, tuple[int, int]],
    ) -> None:
        part_count, previous_lists, html_checkpoint, image_checkpoint = checkpoint
        del parts[part_count:]
        active_lists[:] = previous_lists
        self._html_budget.restore(html_checkpoint)
        self._image_budget.restore(image_checkpoint)

    def _opening_tag(self) -> str:
        return (
            "<div class='docx-preview' "
            f"style=\"font-family:'{escape(self._base_font_name)}',serif;"
            f'font-size:{self._base_font_size_em:.2f}em;">'
        )

    def _append_paragraph(
        self,
        parts: list[str],
        active_lists: list[str],
        markup: ParagraphMarkup,
    ) -> None:
        if not markup.list_tag:
            self._close_lists(parts, active_lists)
            self._html_budget.reserve(
                len(f"<{markup.tag}{markup.style_attr}></{markup.tag}>")
            )
            parts.append(
                f"<{markup.tag}{markup.style_attr}>{markup.inner_html}</{markup.tag}>"
            )
            return
        target_depth = max(1, int(markup.list_level or 0) + 1)
        while len(active_lists) > target_depth:
            parts.append(f"</{active_lists.pop()}>")
        while len(active_lists) < target_depth:
            active_lists.append(markup.list_tag)
            self._html_budget.reserve(len(f"<{markup.list_tag}></{markup.list_tag}>"))
            parts.append(f"<{markup.list_tag}>")
        if active_lists[-1] != markup.list_tag:
            parts.append(f"</{active_lists.pop()}>")
            active_lists.append(markup.list_tag)
            self._html_budget.reserve(len(f"<{markup.list_tag}></{markup.list_tag}>"))
            parts.append(f"<{markup.list_tag}>")
        self._html_budget.reserve(len(f"<li{markup.style_attr}></li>"))
        parts.append(f"<li{markup.style_attr}>{markup.inner_html}</li>")

    @staticmethod
    def _close_lists(parts: list[str], active_lists: list[str]) -> None:
        while active_lists:
            parts.append(f"</{active_lists.pop()}>")


def _iter_blocks(document) -> Iterator[Paragraph | Table]:
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _base_font(document) -> tuple[str, float]:
    font_name = "Times New Roman"
    font_size_pt = 12.0
    try:
        normal_style = document.styles["Normal"]
        if normal_style and normal_style.font:
            font_name = safe_font(normal_style.font.name, font_name)
            if normal_style.font.size:
                font_size_pt = float(normal_style.font.size.pt)
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    font_size_pt = max(9.0, min(18.0, font_size_pt))
    return font_name, max(0.85, min(1.35, font_size_pt / 12.0))


def _table_text_length(table: Table) -> int:
    return sum(len(cell.text or "") for row in table.rows for cell in row.cells)
