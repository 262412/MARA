"""Exercise the renderer itself against pre-extraction HTML without page or IO."""

import ast
import builtins
import copy
import io
import json
import os
import shutil
import socket
from pathlib import Path

from ktem.pages.chat import file_browser_rendering as rendering
from ktem_tests.file_browser_rendering_cases import EXCERPTS, ROWS, SELECTED


def direct_html_cases():
    image_cards = [
        rendering.render_page_thumbnail_card(
            page, 2, rendering.render_image_thumbnail_preview(src, page)
        )
        for page, src in enumerate(
            ["/file=owned/a&b'\".png", "/file=owned/fallback.png", ""], start=1
        )
    ]
    text_cards = [
        rendering.render_page_thumbnail_card(
            page,
            3,
            rendering.render_text_thumbnail_preview(EXCERPTS[page], "al.pha"),
        )
        for page in (1, 3)
    ]
    language = "中文 & <English> '\""
    return {
        "empty_library": rendering.render_chat_file_list([], set()),
        "grouped_library": rendering.render_chat_file_list(ROWS, SELECTED),
        "empty_summary": rendering.render_corpus_summary(0, 0, "0 B", 0),
        "zero_summary": rendering.render_corpus_summary(1, 1, "0 B", 0),
        "regular_summary": rendering.render_corpus_summary(8, 11, "5.5 KB", 2),
        "empty_header": rendering.render_page_strip_header("", "", 1, 0),
        "header": rendering.render_page_strip_header(
            "星 & <tag> '\".png", "Images", 2, 1536
        ),
        "missing_header": rendering.render_page_strip_header(
            "missing.pdf", "PDF", 1, 0
        ),
        "empty_thumbnails": rendering.render_empty_thumbnail_strip(),
        "image_thumbnails": rendering.render_page_thumbnail_list(image_cards),
        "text_thumbnails": rendering.render_page_thumbnail_list(text_cards),
        "no_matching_pages": rendering.render_empty_thumbnail_strip("'<none>&'"),
        "empty_metadata": rendering.render_page_metadata_strip(
            "", "None", 1, 1, "Unavailable", "Not needed", language
        ),
        "image_metadata": rendering.render_page_metadata_strip(
            "星 & <tag> '\".png",
            "Images",
            1,
            2,
            "Available",
            "Needed for scanned pages",
            language,
        ),
        "entity_highlight": rendering.render_text_thumbnail_preview(EXCERPTS[1], "&"),
        "regex_highlight": rendering.render_text_thumbnail_preview(
            EXCERPTS[1], "al.pha"
        ),
        "plain_excerpt": rendering.render_text_thumbnail_preview(EXCERPTS[1], ""),
    }


def test_renderer_has_only_standard_library_dependencies():
    source = Path(rendering.__file__).read_text(encoding="utf-8")
    imports = [
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert imports == ["html", "os", "re"]
    assert not any(
        isinstance(node, ast.ImportFrom) for node in ast.walk(ast.parse(source))
    )


def test_plain_data_renderer_matches_all_old_html_without_io(monkeypatch):
    expected = json.loads(
        Path(__file__)
        .with_name("fixtures")
        .joinpath("file_browser_rendering.json")
        .read_text(encoding="utf-8")
    )["html"]
    original = copy.deepcopy(ROWS)
    calls = []

    def deny(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Rendering must not perform IO")

    # Import the actual package normally, then deny effects during rendering.
    # No parent package or page/runtime object is faked or passed to the renderer.
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", deny)
        patch.setattr(io, "open", deny)
        patch.setattr(os, "stat", deny)
        patch.setattr(os, "getcwd", deny)
        patch.setattr(shutil, "disk_usage", deny)
        patch.setattr(socket.socket, "connect", deny)
        actual = direct_html_cases()
    assert actual == expected
    assert calls == []
    assert ROWS == original
    assert SELECTED == {"pdf'\"<&", "fallback.txt", ""}


def test_legacy_plain_card_markup_and_empty_text_remain_escaped():
    assert rendering._render_simple_file_list(
        [{"id": "x'&", "name": "<&"}], {"x'&"}
    ) == (
        "<div class='chat-file-list-shell'><button type='button' "
        "class='chat-file-entry is-selected' data-chat-file-id='x&#x27;&amp;'>"
        "<span class='chat-file-entry__name'>&lt;&amp;</span></button></div>"
    )
    assert rendering.render_text_thumbnail_preview("", "") == (
        "<span class='page-thumbnail-card__text'>No text preview available.</span>"
    )
