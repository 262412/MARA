"""Fixed inputs captured against R3-C's original ChatPage implementation."""

import os
from types import SimpleNamespace
from typing import Any, cast

import ktem.pages.chat as chat

ROWS = [
    {"id": "doc", "name": "notes.MD", "page_count": 0, "size": 0},
    {"id": "image", "name": "画像.PNG", "size": 1024},
    {"id": "pdf'\"<&", "name": "星 & <tag> '\".PDF", "page_count": 2, "size": 1536},
    {"id": "slides", "name": "talk.pptx", "page_count": -2, "size": 1023},
    {"id": "pdf-2", "name": "second.pdf", "page_count": 1, "size": None},
    {"id": "unknown", "name": "archive.zip", "page_count": "3", "size": "2048"},
    {"id": "fallback.txt", "name": None},
    {},
]
SELECTED = {"pdf'\"<&", "fallback.txt", ""}
EXCERPTS = {1: "AL.PHA <tag> & Ω", 2: "unmatched", 3: "al.pha's second hit"}


def plain_page():
    page = cast(Any, chat.ChatPage.__new__(chat.ChatPage))
    page._app = SimpleNamespace(
        default_settings=SimpleNamespace(
            reasoning=SimpleNamespace(
                settings={"lang": SimpleNamespace(value="中文 & <English> '\"")}
            )
        )
    )
    return page


def fixed_html_cases(monkeypatch):
    """Use data-only operation boundaries; return the original complete HTML."""
    page = plain_page()
    monkeypatch.setattr(
        chat,
        "os",
        SimpleNamespace(
            path=SimpleNamespace(
                splitext=os.path.splitext,
                isfile=lambda path: path == "owned/image.png",
                getsize=lambda _path: 1536,
            ),
            getcwd=lambda: "owned/cwd",
        ),
    )
    monkeypatch.setattr(
        chat, "flowsettings", SimpleNamespace(KH_FILESTORAGE_PATH="owned")
    )
    monkeypatch.setattr(
        chat,
        "shutil",
        SimpleNamespace(disk_usage=lambda _: SimpleNamespace(total=1_000_000)),
    )
    page.page_preview = SimpleNamespace(
        _get_page_thumbnail=lambda _file, number: "/file=owned/a&b'\".png"
        if number == 1
        else "",
        _get_page_preview_image=lambda _file, _path, number: "/file=owned/fallback.png"
        if number == 2
        else "",
    )
    page._get_text_thumbnail_excerpt = lambda _id, _name, _path, number: EXCERPTS[
        number
    ]
    return {
        "empty_library": page._render_chat_file_list_html([], set()),
        "grouped_library": page._render_chat_file_list_html(ROWS, SELECTED),
        "empty_summary": page._render_corpus_summary_html([]),
        "zero_summary": page._render_corpus_summary_html([{}]),
        "regular_summary": page._render_corpus_summary_html(ROWS),
        "empty_header": page._render_page_strip_header(
            "id", "", "owned/image.png", "bad"
        ),
        "header": page._render_page_strip_header(
            "id", "星 & <tag> '\".png", "owned/image.png", 2
        ),
        "missing_header": page._render_page_strip_header(
            "id", "missing.pdf", "missing", None
        ),
        "empty_thumbnails": page._render_page_thumbnail_strip("", "", "", "bad", "bad"),
        "image_thumbnails": page._render_page_thumbnail_strip(
            "pdf", "a.pdf", "owned/a.pdf", 2, 3, "ignored"
        ),
        "text_thumbnails": page._render_page_thumbnail_strip(
            "text", "a.txt", "owned/a.txt", 3, 3, " al.pha "
        ),
        "no_matching_pages": page._render_page_thumbnail_strip(
            "text", "a.txt", "owned/a.txt", 1, 3, " '<none>&' "
        ),
        "empty_metadata": page._render_page_metadata_strip("", "", "", None, 0),
        "image_metadata": page._render_page_metadata_strip(
            "id", "星 & <tag> '\".png", "owned/image.png", 0, 2
        ),
        "entity_highlight": page._render_text_thumbnail_preview(
            "text", "a.txt", "", 1, "&"
        ),
        "regex_highlight": page._render_text_thumbnail_preview(
            "text", "a.txt", "", 1, "al.pha"
        ),
        "plain_excerpt": page._render_text_thumbnail_preview(
            "text", "a.txt", "", 1, ""
        ),
    }
