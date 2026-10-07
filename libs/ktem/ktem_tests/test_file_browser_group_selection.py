"""Group selector values should highlight their files without changing scope."""

from ktem_tests.file_browser_rendering_cases import plain_page


def test_group_selector_highlights_authorized_rows_and_resolves_focus_name():
    page = plain_page()
    calls = []
    rows = [{"id": "a", "name": "A & B.txt"}, {"id": "b", "name": "B.txt"}]
    selection = ['["a", "b"]', "b"]
    page._resolve_persist_user_id = lambda *args: "owner"

    def record(event, result):
        calls.append(event)
        return result

    page._source_rows_for_sidebar = lambda *args: record(("rows", args), rows)
    page._load_available_source_map = lambda *args: record(("fallback", args), {})
    page._render_chat_file_list_html = lambda records, selected: record(
        ("render", records is rows, selected), "selected cards"
    )
    page._render_corpus_summary_html = lambda records: "summary"

    result = page.refresh_chat_file_list("conversation", "owner", [], selection, [], "")

    assert result == (rows, "selected cards", "Focus: A &amp; B.txt", "summary")
    assert calls == [
        ("rows", ("owner", [], [], "conversation", "")),
        ("render", True, {"a", "b"}),
    ]
    assert selection == ['["a", "b"]', "b"]
