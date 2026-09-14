"""Keep original read timing, short circuits and request-aware callback seams."""

import copy
import os
from types import SimpleNamespace
from typing import Any

import ktem.pages.chat as chat
import pytest
from ktem_tests.file_browser_rendering_cases import plain_page


def recorded(calls, event, result):
    calls.append(event)
    return result


def fake_paths(monkeypatch, calls, *, present=True, size=1536):
    def isfile(path):
        calls.append(("isfile", path))
        return present

    def getsize(path):
        calls.append(("getsize", path))
        return size

    def getcwd():
        calls.append(("cwd",))
        return "cwd"

    monkeypatch.setattr(
        chat,
        "os",
        SimpleNamespace(
            path=SimpleNamespace(
                splitext=os.path.splitext, isfile=isfile, getsize=getsize
            ),
            getcwd=getcwd,
        ),
    )


@pytest.mark.parametrize(
    "size,total,expected",
    [
        (0, 100, 0),
        (1, 10000, 2),
        (30, 100, 30),
        (1000, 100, 100),
        (1, 0, 100),
        (-1, 100, 2),
    ],
)
def test_capacity_query_timing_and_original_progress_bounds(
    monkeypatch, size, total, expected
):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls)
    original = page._format_bytes

    def format_bytes(value):
        calls.append(("bytes", value))
        return original(value)

    page._format_bytes = format_bytes

    class Settings:
        @property
        def KH_FILESTORAGE_PATH(self):
            calls.append(("settings",))
            return "storage"

    def disk_usage(path):
        calls.append(("disk", path))
        return SimpleNamespace(total=total)

    monkeypatch.setattr(chat, "flowsettings", Settings())
    monkeypatch.setattr(chat, "shutil", SimpleNamespace(disk_usage=disk_usage))
    result = page._render_corpus_summary_html([{"size": size}])
    assert f"<span style='width: {expected}%'></span>" in result
    expected_calls: list[Any] = [("bytes", size)]
    if size:
        expected_calls += [("cwd",), ("settings",), ("disk", "storage")]
    assert calls == expected_calls


def test_capacity_failure_keeps_full_bar_and_format_error_precedes_query(monkeypatch):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls)
    monkeypatch.setattr(chat, "flowsettings", SimpleNamespace())

    def disk_usage(path):
        calls.append(("disk", path))
        raise OSError("owned unavailable disk")

    monkeypatch.setattr(chat, "shutil", SimpleNamespace(disk_usage=disk_usage))
    assert "width: 100%" in page._render_corpus_summary_html([{"size": 1}])
    assert calls == [("cwd",), ("disk", "cwd")]
    calls.clear()
    with pytest.raises(ValueError):
        page._render_corpus_summary_html([{"size": "invalid"}])
    assert calls == []


@pytest.mark.parametrize(
    "name,path,total,present,expected",
    [
        ("", "owned", "bad", True, []),
        ("a.pdf", "", None, True, []),
        ("a.pdf", "owned", 1, False, [("isfile", "owned")]),
        ("a.pdf", "owned", 1, True, [("isfile", "owned"), ("getsize", "owned")]),
    ],
)
def test_header_empty_and_stat_short_circuits(
    monkeypatch, name, path, total, present, expected
):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls, present=present)
    page._render_page_strip_header("id", name, path, total)
    assert calls == expected


def test_header_bad_page_count_fails_after_stat(monkeypatch):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls)
    with pytest.raises(ValueError):
        page._render_page_strip_header("id", "a.pdf", "owned", "bad")
    assert calls == [("isfile", "owned"), ("getsize", "owned")]


def test_metadata_reads_language_after_existence_even_without_filename(monkeypatch):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls)

    class Settings(dict):
        def get(self, name):
            calls.append(("language", name))
            return None

    page._app.default_settings.reasoning.settings = Settings()
    rendered = page._render_page_metadata_strip("", "", "owned", 1, 1)
    assert "<span>Language</span><strong>default</strong>" in rendered
    assert "No page selected" in rendered
    assert calls == [("isfile", "owned"), ("language", "lang")]
    calls.clear()
    with pytest.raises(ValueError):
        page._render_page_metadata_strip("", "a.pdf", "owned", "bad", 1)
    assert calls == []


def test_text_excerpt_preserves_paginate_limit_clamp_and_extraction_order():
    page = plain_page()
    calls: list[Any] = []
    text = object()
    pages = ["<b>first</b> &amp; Ω", "<p>" + "z" * 300 + "</p>"]

    def extract(path, name):
        calls.append(("extract", path, name))
        return text

    def paginate(value, **kwargs):
        assert value is text
        calls.append(("paginate", kwargs))
        return pages

    page.page_preview = SimpleNamespace(
        _extract_text_from_file=extract, _paginate_plain_text=paginate
    )
    assert page._get_text_thumbnail_excerpt("id", "a.pdf", "owned", 1) == ""
    assert calls == []
    assert page._get_text_thumbnail_excerpt("id", "a.txt", "owned", 0) == "first & Ω"
    assert page._get_text_thumbnail_excerpt("id", "a.txt", "owned", 99) == "z" * 260
    assert (
        calls
        == [("extract", "owned", "a.txt"), ("paginate", {"max_chars_per_page": 1200})]
        * 2
    )
    assert pages[0] == "<b>first</b> &amp; Ω"
    calls.clear()
    with pytest.raises(ValueError):
        page._get_text_thumbnail_excerpt("id", "a.txt", "owned", "bad")
    assert calls == [
        ("extract", "owned", "a.txt"),
        ("paginate", {"max_chars_per_page": 1200}),
    ]
    page.page_preview._paginate_plain_text = lambda *_a, **_k: []
    with pytest.raises(IndexError):
        page._get_text_thumbnail_excerpt("id", "a.txt", "owned", 1)


def test_text_filter_keeps_repeated_reads_and_regex_literal_query():
    page = plain_page()
    calls: list[Any] = []
    excerpts = {1: "A.B alpha", 2: "axb other", 3: "a.b last"}

    def excerpt(_id, _name, _path, number):
        calls.append(number)
        return excerpts[number]

    page._get_text_thumbnail_excerpt = excerpt
    rendered = page._render_page_thumbnail_strip("id", "a.txt", "owned", 3, 3, " A.B ")
    assert calls == [1, 2, 3, 1, 3]
    assert "data-page-number='2'" not in rendered
    assert "<mark>A.B</mark>" in rendered and "<mark>a.b</mark>" in rendered
    calls.clear()
    assert page._render_page_thumbnail_strip(
        "id", "a.txt", "owned", 1, 3, "<missing>"
    ) == ("<div class='page-thumbnail-empty'>No pages match '&lt;missing&gt;'.</div>")
    assert calls == [1, 2, 3]
    calls.clear()
    page._render_page_thumbnail_strip("id", "a.txt", "owned", 1, 3, " ")
    assert calls == [1, 2, 3]


def test_thumbnail_hit_skips_fallback_and_error_stops_later_pages():
    page = plain_page()
    calls: list[Any] = []

    def thumbnail(file_id, number):
        calls.append(("thumbnail", file_id, number))
        return "owned-hit" if number == 1 else ""

    def fallback(file_id, path, number):
        calls.append(("image", file_id, path, number))
        return "owned-fallback" if number == 2 else ""

    page.page_preview = SimpleNamespace(
        _get_page_thumbnail=thumbnail, _get_page_preview_image=fallback
    )
    rendered = page._render_page_thumbnail_strip("id", "a.pdf", "owned", 2, 3)
    assert calls == [
        ("thumbnail", "id", 1),
        ("thumbnail", "id", 2),
        ("image", "id", "owned", 2),
        ("thumbnail", "id", 3),
        ("image", "id", "owned", 3),
    ]
    assert rendered.count("<img ") == 2
    assert "<span class='page-thumbnail-card__page'></span>" in rendered
    calls.clear()

    def fail(*args):
        calls.append(("failure", *args))
        raise PermissionError("preview denied")

    page.page_preview._get_page_preview_image = fail
    with pytest.raises(PermissionError, match="preview denied"):
        page._render_page_thumbnail_strip("id", "a.pdf", "owned", 1, 4)
    assert calls == [
        ("thumbnail", "id", 1),
        ("thumbnail", "id", 2),
        ("failure", "id", "owned", 2),
    ]


@pytest.mark.parametrize("getter", [None, "not callable"])
def test_absent_thumbnail_getter_uses_existing_image_boundary(getter):
    page = plain_page()
    calls: list[Any] = []
    page.page_preview = SimpleNamespace(
        _get_page_preview_image=lambda *args: recorded(calls, args, "")
    )
    if getter is not None:
        page.page_preview._get_page_thumbnail = getter
    page._render_page_thumbnail_strip("id", "a.pdf", "owned", 1, None)
    assert calls == [("id", "owned", 1)]


def test_sidebar_filters_before_source_io_and_does_not_mutate_records(monkeypatch):
    page = plain_page()
    calls: list[Any] = []
    fake_paths(monkeypatch, calls)
    records = {
        "skip": {"name": "skip.pdf", "size": "bad"},
        "keep": {"name": "Focus.txt", "size": 0, "nested": []},
    }
    original = copy.deepcopy(records)
    page._load_available_source_records = lambda user: recorded(
        calls, ("records", user), records
    )
    page._resolve_source_file_path = lambda file_id, user: recorded(
        calls, ("resolve", file_id, user), "owned"
    )
    page._count_source_pages = lambda *args: recorded(calls, ("pages", *args), 4)
    rows = page._source_rows_for_sidebar(
        "owner", [["Victim", "forged"]], ["skip"], "conv", "focus"
    )
    assert rows == [
        {
            "id": "keep",
            "name": "Focus.txt",
            "path": "owned",
            "size": 1536,
            "page_count": 4,
        }
    ]
    assert records == original
    assert calls == [
        ("records", "owner"),
        ("resolve", "keep", "owner"),
        ("isfile", "owned"),
        ("getsize", "owned"),
        ("pages", "keep", "Focus.txt", "owned"),
    ]


def test_refresh_uses_request_identity_first_and_keeps_filtered_selection_fallback():
    page = plain_page()
    calls: list[Any] = []
    request, selected, graph = object(), ["hidden"], ["graph"]
    choices: list[Any] = []
    rows = [{"id": "visible", "name": "Visible.txt"}]
    page._resolve_persist_user_id = lambda user, actual: recorded(
        calls, ("identity", user, actual), "owner"
    )

    def source_rows(user, actual_choices, scope, conversation, query):
        assert actual_choices is choices
        calls.append(("rows", user, scope, conversation, query))
        return rows

    page._source_rows_for_sidebar = source_rows
    page._load_available_source_map = lambda user: recorded(
        calls, ("fallback", user), {"hidden": "Hidden & File"}
    )
    page._render_chat_file_list_html = lambda actual, ids: recorded(
        calls, ("render", actual is rows, ids), "list"
    )
    page._render_corpus_summary_html = lambda actual: recorded(
        calls, ("summary", actual is rows), "summary"
    )
    result = page.refresh_chat_file_list(
        "conv", "forged", choices, selected, graph, " FOCUS ", request=request
    )
    assert result == (rows, "list", "Focus: Hidden & File", "summary")
    assert result[0] is rows and selected == ["hidden"] and graph == ["graph"]
    assert calls == [
        ("identity", "forged", request),
        ("rows", "owner", [], "conv", "focus"),
        ("fallback", "owner"),
        ("render", True, {"hidden"}),
        ("summary", True),
    ]
    calls.clear()

    def deny(*args):
        calls.append(("denied", *args))
        raise PermissionError("identity missing")

    page._resolve_persist_user_id = deny
    with pytest.raises(PermissionError, match="identity missing"):
        page.refresh_chat_file_list(
            "conv", None, choices, [], graph, "", request=request
        )
    assert calls == [("denied", None, request)]


def test_context_resolves_authorized_source_before_all_three_renderers():
    page = plain_page()
    calls: list[Any] = []
    request = object()

    def resolve(file_id, actual):
        calls.append(("resolve", file_id, actual))
        return "Authorized.pdf", "authorized/path"

    page.page_preview = SimpleNamespace(_resolve_callback_source=resolve)
    page._render_page_strip_header = lambda *args: recorded(
        calls, ("header", *args), "header"
    )
    page._render_page_thumbnail_strip = lambda *args: recorded(
        calls, ("strip", *args), "strip"
    )
    page._render_page_metadata_strip = lambda *args: recorded(
        calls, ("metadata", *args), "metadata"
    )
    result = page.refresh_page_context_view(
        "id", "forged.pdf", "forged/path", 2, 3, "query", request=request
    )
    assert result == ("header", "strip", "metadata")
    assert calls == [
        ("resolve", "id", request),
        ("header", "id", "Authorized.pdf", "authorized/path", 3),
        ("strip", "id", "Authorized.pdf", "authorized/path", 2, 3, "query"),
        ("metadata", "id", "Authorized.pdf", "authorized/path", 2, 3),
    ]
    calls.clear()

    def missing(*args):
        calls.append(("missing", *args))
        raise PermissionError("source unavailable")

    page.page_preview._resolve_callback_source = missing
    with pytest.raises(PermissionError, match="source unavailable"):
        page.refresh_page_context_view(
            "id", "forged.pdf", "forged/path", 2, 3, request=request
        )
    assert calls == [("missing", "id", request)]
