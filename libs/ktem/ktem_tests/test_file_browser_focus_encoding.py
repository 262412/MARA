"""Untrusted file names must stay text in the Markdown focus component."""

import pytest
from ktem_tests.file_browser_rendering_cases import plain_page


@pytest.mark.parametrize("filtered_out", [False, True])
def test_focus_label_encodes_file_name_from_row_or_authorized_fallback(filtered_out):
    page = plain_page()
    name = '星 & <img src="/r3c-exfil" onerror="globalThis.r3cInjected=1">.txt'
    rows = [] if filtered_out else [{"id": "owned", "name": name}]
    page._resolve_persist_user_id = lambda *_: "owner"
    page._source_rows_for_sidebar = lambda *_: rows
    page._load_available_source_map = lambda _: {"owned": name}
    page._render_chat_file_list_html = lambda *_: "list"
    page._render_corpus_summary_html = lambda *_: "summary"
    result = page.refresh_chat_file_list("conv", "owner", [], ["owned"], [], "")
    assert result[2] == (
        "Focus: 星 &amp; &lt;img src=&quot;/r3c-exfil&quot; "
        "onerror=&quot;globalThis.r3cInjected=1&quot;&gt;.txt"
    )
    assert result[0] is rows
