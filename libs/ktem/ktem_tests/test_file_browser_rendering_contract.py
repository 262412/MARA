"""Characterize old HTML, lexical formatting and component outputs before extraction."""

import copy
import inspect
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest
from ktem.pages.chat import ChatPage
from ktem_tests.file_browser_rendering_cases import (
    ROWS,
    SELECTED,
    fixed_html_cases,
    plain_page,
)

GOLDEN = Path(__file__).with_name("fixtures") / "file_browser_rendering.json"


def test_complete_html_matches_the_original_source_capture(monkeypatch):
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert expected["source"] == "742c3e0b5a654a37126c2ef6d2bb9344f5e05d1e"
    before = copy.deepcopy(ROWS)
    actual = fixed_html_cases(monkeypatch)
    assert actual == expected["html"]
    assert ROWS == before
    assert SELECTED == {"pdf'\"<&", "fallback.txt", ""}


def test_library_dom_preserves_group_order_row_order_and_attribute_text(monkeypatch):
    root = ElementTree.fromstring(fixed_html_cases(monkeypatch)["grouped_library"])
    assert root.attrib == {"class": "corpus-file-library"}
    assert [section.findall("div/strong")[0].text for section in root] == [
        "PDF",
        "Images",
        "Slides",
        "Documents",
    ]
    buttons = list(root.iter("button"))
    assert [button.attrib["data-chat-file-id"] for button in buttons] == [
        "pdf'\"<&",
        "pdf-2",
        "image",
        "slides",
        "doc",
        "unknown",
        "fallback.txt",
        "",
    ]
    assert [
        button.attrib["data-chat-file-id"]
        for button in buttons
        if button.attrib["class"] == "corpus-file-entry is-selected"
    ] == ["pdf'\"<&", "fallback.txt", ""]
    assert (
        next(root.iter("button"))
        .findall("span[@class='corpus-file-entry__body']/span")[0]
        .text
        == "星 & <tag> '\".PDF"
    )
    assert not list(root.iter("tag"))
    assert all(
        set(button.attrib) == {"type", "class", "data-chat-file-id"}
        for button in buttons
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        (None, "Documents"),
        ("", "Documents"),
        (123, "Documents"),
        ("x.PDF", "PDF"),
        ("x.ppt", "Slides"),
        ("x.PPTX", "Slides"),
        *[
            ("x." + suffix, "Images")
            for suffix in ("png", "jpg", "jpeg", "gif", "webp", "svg")
        ],
        *[
            ("x." + suffix, "Documents")
            for suffix in ("doc", "docx", "txt", "md", "rtf", "zip", "html")
        ],
    ],
)
def test_file_type_fixed_values(name, expected):
    assert ChatPage._format_corpus_file_type(name) == expected


@pytest.mark.parametrize(
    "size,expected",
    [
        (None, "0 B"),
        (0, "0 B"),
        (0.9, "0 B"),
        (-1, "-1 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024**2 - 1, "1024.0 KB"),
        (1024**2, "1.0 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
        (1024**5, "1024.0 TB"),
        ("2048", "2.0 KB"),
        (float("inf"), "inf TB"),
        (float("nan"), "nan TB"),
    ],
)
def test_byte_unit_boundaries(size, expected):
    assert ChatPage._format_bytes(size) == expected


@pytest.mark.parametrize(
    "size,error", [("invalid", ValueError), ([], None), ({1: 2}, TypeError)]
)
def test_byte_conversion_exception_contract(size, error):
    if error is None:
        assert ChatPage._format_bytes(size) == "0 B"
    else:
        with pytest.raises(error):
            ChatPage._format_bytes(size)


@pytest.mark.parametrize(
    "name,pages,expected",
    [
        ("photo.svg", None, "1 page"),
        ("photo.png", 0, "1 page"),
        ("a.pdf", None, "page count unavailable"),
        ("a.pdf", 0, "page count unavailable"),
        ("a.pdf", -1, "1 page"),
        ("a.pdf", 1, "1 page"),
        ("a.pdf", "0", "1 page"),
        ("a.pdf", "3", "3 pages"),
        ("a.pdf", 2.9, "2 pages"),
        ("", None, "page count unavailable"),
    ],
)
def test_page_meta_fixed_values(name, pages, expected):
    assert plain_page()._format_corpus_file_meta(name, pages) == expected


def test_conversion_errors_are_not_silently_changed_to_defaults():
    page = plain_page()
    with pytest.raises(ValueError):
        page._format_corpus_file_meta("a.pdf", "invalid")
    with pytest.raises(ValueError):
        page._render_chat_file_list_html([{"id": "id", "size": "invalid"}], set())
    with pytest.raises(ValueError):
        page._render_corpus_summary_html([{"page_count": "invalid"}])
    with pytest.raises(TypeError):
        page._format_bytes(object())


def test_staticmethod_and_original_public_signatures():
    for name in (
        "_format_corpus_file_type",
        "_format_bytes",
        "_is_text_thumbnail_source",
        "_plain_text_from_preview_html",
    ):
        assert isinstance(ChatPage.__dict__[name], staticmethod)
    assert list(inspect.signature(ChatPage.refresh_chat_file_list).parameters) == [
        "self",
        "conversation_id",
        "user_id",
        "first_selector_choices",
        "selected_file_ids",
        "graph_source_ids",
        "filter_text",
        "request",
    ]
    assert list(inspect.signature(ChatPage.refresh_page_context_view).parameters) == [
        "self",
        "file_id",
        "file_name",
        "file_path",
        "page_number",
        "total_pages",
        "filter_text",
        "request",
    ]
    assert list(inspect.signature(ChatPage.select_chat_file).parameters) == [
        "self",
        "file_id",
    ]


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ({"__type__": "update"}, {"__type__": "update"}, "")),
        ("  ", ({"__type__": "update"}, {"__type__": "update"}, "")),
        (" id ", ("select", {"__type__": "update", "value": ["id"]}, "")),
        (42, ("select", {"__type__": "update", "value": ["42"]}, "")),
    ],
)
def test_card_selection_keeps_three_outputs_and_no_update_distinction(value, expected):
    assert plain_page().select_chat_file(value) == expected
