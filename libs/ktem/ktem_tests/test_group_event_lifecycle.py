"""A newly published group list must not have an older close still pending."""

import pytest
from ktem.index.file._events import register_file_index_events

from .test_file_index_page_extraction import _build_page


@pytest.mark.parametrize("button_name", ["group_save_button", "group_delete_button"])
def test_close_precedes_the_next_selectable_group_list(button_name):
    page = _build_page(index_id=1)
    register_file_index_events(page, demo_mode=False, sso_enabled=False)
    chain = getattr(page, button_name).calls
    assert chain[1][1]["outputs"][-1] is page.selected_group_id
    assert chain[1][1]["fn"]() == [
        {"__type__": "update", "visible": True},
        *[{"__type__": "update", "visible": False} for _ in range(4)],
        None,
    ]
    assert chain[2][1]["fn"] is page.list_group
    assert chain[2][1]["inputs"] == [page._app.user_id, page.file_list_state]
    assert chain[2][1]["outputs"] == [page.group_list_state, page.group_list]
    assert chain[3] == ("then", {"fn": "public-event"})
