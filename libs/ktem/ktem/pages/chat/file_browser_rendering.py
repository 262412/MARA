"""File-library and page-navigation presentation from already-resolved data.

Source access, file reads and preview generation remain in the page adapters.
URI attribute encoding here does not authorize a preview source.
"""

import html
import os
import re


def format_corpus_file_type(file_name: str) -> str:
    suffix = os.path.splitext(str(file_name or "").lower())[1]
    if suffix == ".pdf":
        return "PDF"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "Images"
    if suffix in {".ppt", ".pptx"}:
        return "Slides"
    if suffix in {".doc", ".docx", ".txt", ".md", ".rtf"}:
        return "Documents"
    return "Documents"


def format_bytes(size_bytes: int | float | None) -> str:
    size = float(size_bytes or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "0 B"


def format_corpus_file_meta(file_name: str, page_count=None) -> str:
    if page_count:
        pages = max(1, int(page_count))
        return f"{pages} page" if pages == 1 else f"{pages} pages"
    suffix = os.path.splitext(str(file_name or "").lower())[1]
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "1 page"
    return "page count unavailable"


def render_corpus_summary(
    file_count: int, page_count: int, storage_label: str, width: int
) -> str:
    file_label = "file" if file_count == 1 else "files"
    page_label = "page" if page_count == 1 else "pages"
    return (
        "<div class='workbench-file-summary'>"
        "<div>"
        f"<strong>{file_count} {file_label}</strong>"
        f"<span>{page_count} {page_label}</span>"
        "</div>"
        "<div>"
        f"<strong>{html.escape(storage_label)}</strong>"
        "<span>stored</span>"
        "</div>"
        "<div class='workbench-file-summary__bar'>"
        f"<span style='width: {width}%'></span>"
        "</div>"
        "</div>"
    )


def render_chat_file_list(rows: list[dict], selected_ids: set[str]) -> str:
    if not rows:
        return "<div class='chat-file-empty'>No files uploaded</div>"

    grouped_rows: dict[str, list[dict]] = {
        "PDF": [],
        "Images": [],
        "Slides": [],
        "Documents": [],
    }
    for row in rows:
        file_name = str(row.get("name", "") or row.get("id", ""))
        grouped_rows[format_corpus_file_type(file_name)].append(row)

    sections = []
    for file_type, type_rows in grouped_rows.items():
        if not type_rows:
            continue
        sections.append(_render_file_section(file_type, type_rows, selected_ids))
    if sections:
        return "<div class='corpus-file-library'>" + "".join(sections) + "</div>"
    return _render_simple_file_list(rows, selected_ids)


def _render_file_section(file_type, type_rows, selected_ids) -> str:
    items = []
    for row in type_rows:
        file_id = str(row.get("id", "") or "")
        file_name = str(row.get("name", "") or file_id)
        is_selected = file_id in selected_ids
        item_class = (
            "corpus-file-entry is-selected" if is_selected else "corpus-file-entry"
        )
        page_meta = format_corpus_file_meta(file_name, row.get("page_count"))
        size_meta = format_bytes(int(row.get("size", 0) or 0))
        items.append(
            "<button type='button' "
            f"class='{item_class}' "
            f"data-chat-file-id='{html.escape(file_id, quote=True)}'>"
            "<span class='corpus-file-entry__icon'>"
            f"{html.escape(file_type[:3].upper())}"
            "</span>"
            "<span class='corpus-file-entry__body'>"
            "<span class='corpus-file-entry__name'>"
            f"{html.escape(file_name)}"
            "</span>"
            "<span class='corpus-file-entry__meta'>"
            f"{html.escape(page_meta)} - {html.escape(size_meta)}"
            "</span>"
            "</span>"
            "<span class='corpus-file-entry__status'>Indexed</span>"
            "</button>"
        )

    return (
        "<section class='corpus-file-section'>"
        "<div class='corpus-file-section__header'>"
        f"<strong>{html.escape(file_type)}</strong>"
        f"<span>{len(type_rows)}</span>"
        "</div>"
        "<div class='corpus-file-section__items'>" + "".join(items) + "</div>"
        "</section>"
    )


def _render_simple_file_list(rows, selected_ids) -> str:
    items = []
    for row in rows:
        file_id = str(row.get("id", "") or "")
        file_name = str(row.get("name", "") or file_id)
        is_selected = file_id in selected_ids
        item_class = "chat-file-entry is-selected" if is_selected else "chat-file-entry"
        items.append(
            "<button type='button' "
            f"class='{item_class}' "
            f"data-chat-file-id='{html.escape(file_id, quote=True)}'>"
            "<span class='chat-file-entry__name'>"
            f"{html.escape(file_name)}"
            "</span>"
            "</button>"
        )

    return "<div class='chat-file-list-shell'>" + "".join(items) + "</div>"


def render_page_strip_header(file_name, file_type, pages, size) -> str:
    if not file_name:
        return "<div class='page-strip-empty'>Select a file to preview pages.</div>"
    page_label = "page" if pages == 1 else "pages"
    return (
        "<div class='page-strip-header'>"
        f"<div class='page-strip-file-icon'>{html.escape(file_type[:3].upper())}</div>"
        "<div>"
        f"<strong>{html.escape(file_name)}</strong>"
        f"<span>{pages} {page_label} - {html.escape(format_bytes(size))}</span>"
        "</div>"
        "<span class='page-strip-indexed'>Indexed</span>"
        "</div>"
    )


def render_text_thumbnail_preview(excerpt: str, query: str) -> str:
    if not excerpt:
        excerpt = "No text preview available."
    if query:
        pattern = re.compile(re.escape(query), flags=re.IGNORECASE)
        excerpt = pattern.sub(
            lambda match: f"<mark>{html.escape(match.group(0))}</mark>",
            html.escape(excerpt),
        )
    else:
        excerpt = html.escape(excerpt)
    return f"<span class='page-thumbnail-card__text'>{excerpt}</span>"


def render_empty_thumbnail_strip(query: str = "") -> str:
    if query:
        return (
            "<div class='page-thumbnail-empty'>"
            f"No pages match '{html.escape(query)}'."
            "</div>"
        )
    return "<div class='page-thumbnail-empty'>No file selected.</div>"


def render_image_thumbnail_preview(preview_src: str, page: int) -> str:
    if preview_src:
        return (
            "<img class='page-thumbnail-card__image' "
            "loading='lazy' "
            f"src='{html.escape(preview_src, quote=True)}' "
            f"alt='Page {page} preview' />"
        )
    return "<span class='page-thumbnail-card__page'></span>"


def render_page_thumbnail_card(page: int, current_page: int, preview: str) -> str:
    classes = ["page-thumbnail-card"]
    if page == current_page:
        classes.append("is-active")
    return (
        "<button type='button' "
        f"class='{' '.join(classes)}' "
        f"data-page-number='{page}'>"
        f"<span class='page-thumbnail-card__num'>{page}</span>"
        f"{preview}"
        f"<strong>Page {page}</strong>"
        "</button>"
    )


def render_page_thumbnail_list(cards: list[str]) -> str:
    return "<div class='page-thumbnail-list'>" + "".join(cards) + "</div>"


def render_page_metadata_strip(
    file_name, file_type, current_page, total, extracted, ocr_state, language
) -> str:
    summary = (
        f"Previewing {html.escape(file_name)}" if file_name else "No page selected"
    )
    return (
        "<div class='page-metadata-strip'>"
        f"<div><span>Modality</span><strong>{html.escape(file_type)}</strong></div>"
        f"<div><span>Page</span><strong>{current_page} / {total}</strong></div>"
        f"<div><span>Page Summary</span><strong>{summary}</strong></div>"
        f"<div><span>Extracted Text</span><strong>{html.escape(extracted)}</strong></div>"
        f"<div><span>OCR</span><strong>{html.escape(ocr_state)}</strong></div>"
        f"<div><span>Language</span><strong>{html.escape(str(language))}</strong></div>"
        "</div>"
    )
