"""Rendering helpers for the page-level answer panel."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import markdown


@dataclass(frozen=True)
class _MathSpan:
    placeholder: str
    source: str
    latex: str
    display: bool


def format_chat_message_html(content: str, role: str) -> str:
    """Format one answer-panel chat message as safe HTML."""
    if role == "assistant":
        formatted_content = _render_assistant_markdown(content)
    else:
        formatted_content = html.escape(content).replace("\n", "<br>")

    return (
        f'<div class="chat-message {role}">'
        f'<div class="chat-message-content">{formatted_content}</div>'
        "</div>"
    )


def _render_assistant_markdown(content: str) -> str:
    content = _normalize_model_line_breaks(content)
    protected_content, math_spans = _extract_math_spans(content)
    normalized_content = _normalize_markdown_tables(protected_content)
    rendered = markdown.markdown(
        html.escape(normalized_content),
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.nl2br",
        ],
    )
    for span in math_spans:
        rendered = rendered.replace(span.placeholder, _render_math_source(span))
    return rendered


def _render_math_source(span: _MathSpan) -> str:
    display = "true" if span.display else "false"
    css_class = (
        "ktem-math-source ktem-math-source--display"
        if span.display
        else "ktem-math-source"
    )
    return (
        f'<span class="{css_class}" data-ktem-display="{display}" '
        f'data-ktem-latex="{html.escape(span.latex, quote=True)}">'
        f"{html.escape(span.source)}</span>"
    )


def _extract_math_spans(content: str) -> tuple[str, list[_MathSpan]]:
    spans: list[_MathSpan] = []
    output: list[str] = []
    index = 0
    while index < len(content):
        match = _find_next_math(content, index)
        if match is None:
            output.append(content[index:])
            break

        start, end, latex_start, latex_end, display = match
        output.append(content[index:start])
        placeholder = f"KTEMMATH{len(spans)}TOKEN"
        source = content[start:end]
        spans.append(
            _MathSpan(
                placeholder=placeholder,
                source=source,
                latex=_normalize_latex(content[latex_start:latex_end], display),
                display=display,
            )
        )
        output.append(placeholder)
        index = end
    return "".join(output), spans


def _normalize_model_line_breaks(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
    normalized = re.sub(r"(?i)&lt;br\s*/?&gt;", "\n", normalized)
    return normalized


def _normalize_latex(latex: str, display: bool) -> str:
    stripped = latex.strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not display or len(lines) <= 1 or "\\begin" in stripped or "\\\\" in stripped:
        return stripped
    aligned_lines = [_align_equation_line(line) for line in lines]
    return "\\begin{aligned}\n" + " \\\\\n".join(aligned_lines) + "\n\\end{aligned}"


def _align_equation_line(line: str) -> str:
    if "&" in line:
        return line
    for operator in ("=", "\\le", "\\ge", "\\approx", "\\sim", "<", ">"):
        index = line.find(operator)
        if index > 0:
            return (
                f"{line[:index].rstrip()} &{operator} "
                f"{line[index + len(operator):].lstrip()}"
            )
    return line


def _find_next_math(text: str, start_at: int) -> tuple[int, int, int, int, bool] | None:
    index = start_at
    while index < len(text):
        if text.startswith("$$", index) and not _is_escaped(text, index):
            closing = _find_closing(text, "$$", index + 2)
            if closing >= 0:
                return index, closing + 2, index + 2, closing, True
            index += 2
            continue
        if text.startswith("\\[", index):
            closing = text.find("\\]", index + 2)
            if closing >= 0:
                return index, closing + 2, index + 2, closing, True
        if text.startswith("\\(", index):
            closing = text.find("\\)", index + 2)
            if closing >= 0:
                return index, closing + 2, index + 2, closing, False
        if text[index] == "$" and not _is_escaped(text, index):
            closing = _find_closing(text, "$", index + 1)
            if closing >= 0:
                return index, closing + 1, index + 1, closing, False
        index += 1
    return None


def _find_closing(text: str, delimiter: str, start_at: int) -> int:
    index = start_at
    while True:
        index = text.find(delimiter, index)
        if index < 0:
            return -1
        if delimiter == "$" and text.startswith("$$", index):
            index += 2
            continue
        if not _is_escaped(text, index):
            return index
        index += len(delimiter)


def _is_escaped(text: str, index: int) -> bool:
    slash_count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        slash_count += 1
        cursor -= 1
    return slash_count % 2 == 1


def _normalize_markdown_tables(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if (
            index + 1 < len(lines)
            and _is_table_row(lines[index])
            and _is_table_separator(lines[index + 1])
        ):
            if output and output[-1].strip():
                output.append("")
            while index < len(lines) and _is_table_row(lines[index]):
                output.append(lines[index])
                index += 1
            if index < len(lines) and lines[index].strip():
                output.append("")
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and not stripped.startswith("```")


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))
