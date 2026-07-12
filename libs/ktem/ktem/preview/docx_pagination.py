from __future__ import annotations

import re

_BLOCK_PATTERN = re.compile(
    r"(<table[^>]*>.*?</table>|<h[1-3][^>]*>.*?</h[1-3]>|"
    r"<p[^>]*>.*?</p>|<li[^>]*>.*?</li>|<ul>|</ul>|<ol>|</ol>)",
    flags=re.DOTALL,
)
_MAX_PAGE_HEIGHT = 980.0


def paginate_docx_html(rich_html: str) -> list[str]:
    if not rich_html:
        return []
    match = re.search(
        r"^<div class='docx-preview'[^>]*>(.*)</div>$",
        rich_html,
        flags=re.DOTALL,
    )
    if not match:
        return [rich_html]
    blocks = _BLOCK_PATTERN.findall(match.group(1))
    if not blocks:
        return [rich_html]
    pages: list[str] = []
    current: list[str] = []
    current_height = 0.0
    for block in blocks:
        block_height = _estimate_block_height(block)
        force_break = "docx-page-break" in block
        if current and current_height + block_height > _MAX_PAGE_HEIGHT:
            pages.append(_wrap_page(current))
            current = []
            current_height = 0.0
        current.append(block)
        current_height += block_height
        if force_break:
            pages.append(_wrap_page(current))
            current = []
            current_height = 0.0
    if current:
        pages.append(_wrap_page(current))
    return pages


def _estimate_block_height(block_html: str) -> float:
    block = block_html.strip().lower()
    if block in {"<ul>", "</ul>", "<ol>", "</ol>"}:
        return 6.0
    text_length = len(_strip_tags(block_html).strip())
    if block.startswith("<h1"):
        chars_per_line, line_height, base = 34, 34.0, 24.0
    elif block.startswith("<h2"):
        chars_per_line, line_height, base = 40, 30.0, 20.0
    elif block.startswith("<h3"):
        chars_per_line, line_height, base = 46, 27.0, 16.0
    elif block.startswith("<li"):
        chars_per_line, line_height, base = 62, 24.0, 8.0
    else:
        chars_per_line, line_height, base = 72, 24.0, 10.0
    lines = max(1, (text_length + chars_per_line - 1) // chars_per_line)
    lines += block_html.lower().count("<br")
    height = base + lines * line_height
    if "docx-page-break" in block_html:
        height += 1200.0
    return height


def _strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    return re.sub(r"<[^>]+>", "", text)


def _wrap_page(blocks: list[str]) -> str:
    return "<div class='docx-preview'>" + "".join(blocks) + "</div>"
