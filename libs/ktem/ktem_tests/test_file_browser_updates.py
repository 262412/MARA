"""The presentation gate preserves old callbacks, identity and side effects."""

from types import SimpleNamespace

import gradio as gr
import pytest
from ktem.pages.chat.file_browser_updates import (
    CAPTURE_SELECTOR_JS,
    chat_file_refresh_event,
    file_browser_result,
    file_selection_result,
    file_selector_result,
    quick_upload_result,
)


def test_file_result_calls_old_patch_once_with_exact_request_and_values():
    calls = []
    rows: list[dict] = []
    selected, graph, choices = ["a"], ["b"], [("A", "a")]
    outputs = (rows, "<div>cards</div>", "Focus", "summary")
    request = gr.Request(username="owner", session_hash="browser-a")
    stamp = {"epoch": "a", "fileRequest": 7}

    def old_entry(*args, **kwargs):
        calls.append((args, kwargs))
        return outputs

    callback = file_browser_result(old_entry)
    result = callback(
        "conversation", "forged-id", choices, selected, graph, "A", stamp, request
    )

    assert calls == [
        (
            ("conversation", "forged-id", choices, selected, graph, "A"),
            {"request": request},
        )
    ]
    assert result["stamp"] is stamp
    assert result["outputs"] is outputs
    assert result["selected"] is selected
    assert result["filter"] == "A"
    assert result["conversation"] == "conversation"
    assert callback.__name__ == old_entry.__name__
    assert callback.__annotations__["request"] is gr.Request


@pytest.mark.parametrize(
    "adapter, args",
    [
        (file_browser_result, ("c", "u", [], [], [], "", {})),
        (lambda fn: file_selector_result(fn, lambda *_: None), ([], "u", {}, {})),
    ],
)
def test_authentication_and_query_errors_propagate_without_presenting_a_result(
    adapter, args
):
    calls = []
    error = gr.Error("Identity is invalid")

    def old_entry(*args, **kwargs):
        calls.append((args, kwargs))
        raise error

    with pytest.raises(gr.Error) as raised:
        adapter(old_entry)(*args, request=gr.Request(username="missing"))
    assert raised.value is error
    assert len(calls) == 1


def test_selector_result_uses_only_authorized_options_and_preserves_old_update():
    selected = ["a", "deleted"]
    options = [("A", "a"), ("group: 'G'", '["a"]')]
    update = gr.update(value=["a"], choices=options)
    calls = []
    request = gr.Request(username="owner")

    def old_entry(files, user_id, request):
        calls.append((files, user_id, request))
        return update, options

    applied = []
    result = file_selector_result(old_entry, lambda *args: applied.append(args))(
        selected, "client-id", {"epoch": "a"}, {}, request
    )
    assert calls == [(selected, "client-id", request)]
    assert result["selected"] is selected
    assert result["update"] is update
    assert result["options"] is options
    assert result["available_ids"] == ["a", '["a"]']
    assert selected == ["a", "deleted"]
    assert applied == [({"epoch": "a"}, options, {})]


def test_refresh_event_preserves_old_six_inputs_then_captures_browser_intent():
    def patch(*args, **kwargs):
        return [], "cards", "focus", "summary"

    page = SimpleNamespace(
        refresh_chat_file_list=patch,
        file_index=SimpleNamespace(id=9),
        chat_control=SimpleNamespace(conversation_id="conversation"),
        _app=SimpleNamespace(user_id="user"),
        first_selector_choices="choices",
        _indices_input=["mode", "selected"],
        _graph_source_ids="graph",
        chat_file_filter="filter",
        _file_browser_stamp="stamp",
        _file_browser_result="result",
    )
    event = chat_file_refresh_event(page)
    assert event["inputs"] == [
        "conversation",
        "user",
        "choices",
        "selected",
        "graph",
        "filter",
        "stamp",
    ]
    assert event["outputs"] == ["result"]
    assert "captureFiles(9)" in event["js"]
    assert event["fn"](None, None, [], [], [], "", {}, gr.Request())["outputs"] == (
        [],
        "cards",
        "focus",
        "summary",
    )
    assert "captureSelector(INDEX_ID, INDEX_CHANGED)" in CAPTURE_SELECTOR_JS


def test_gradio_choice_metadata_is_session_local_and_rejects_reverse_delivery():
    from threading import Lock

    from gradio.context import LocalContext
    from gradio.state_holder import SessionState
    from ktem.index.file._selector_ui import FileSelector

    blocks = gr.Blocks(analytics_enabled=False)
    dropdown = gr.Dropdown(choices=[], value=[], multiselect=True, render=False)
    blocks.blocks[dropdown._id] = dropdown
    selector = FileSelector.__new__(FileSelector)
    selector.selector = dropdown
    selector._choices_lock = Lock()
    a, b = SessionState(blocks), SessionState(blocks)
    applied_a: dict[str, str | int] = {}
    applied_b: dict[str, str | int] = {}
    initial = {"epoch": "a", "selectorRequest": 1}
    latest = {"epoch": "a", "selectorRequest": 2}
    token = LocalContext.blocks_config.set(a.blocks_config)
    try:
        FileSelector._apply_file_choices(selector, latest, [("A", "a")], applied_a)
        FileSelector._apply_file_choices(selector, initial, [("Old", "old")], applied_a)
        assert a[dropdown._id].choices == [("A", "a")]
        assert a[dropdown._id].constructor_args["choices"] == [("A", "a")]
        assert b[dropdown._id].choices == dropdown.choices == []
        LocalContext.blocks_config.set(b.blocks_config)
        FileSelector._apply_file_choices(selector, initial, [("B", "b")], applied_b)
        assert b[dropdown._id].choices == [("B", "b")]
        assert a[dropdown._id].choices == [("A", "a")]
    finally:
        LocalContext.blocks_config.reset(token)
    with pytest.raises(RuntimeError, match="active Gradio session"):
        FileSelector._apply_file_choices(selector, initial, [], {})


def test_index_result_carries_the_same_request_intent_without_repeating_indexing():
    calls = []
    ids, source, stamp = ["new"], ["owned.txt"], {"viewVersion": 7}
    settings: dict[str, object] = {}
    request = gr.Request(username="real-owner")

    def index(*args, **kwargs):
        calls.append((args, kwargs))
        return ids

    legacy, payload = quick_upload_result(index)(
        source, False, settings, "claimed", stamp, "c", request
    )
    assert calls == [((source, False, settings, "claimed"), {"request": request})]
    assert legacy is payload["ids"] is ids
    assert payload["stamp"] is stamp
    assert payload["conversation"] == "c"


def test_card_selection_keeps_the_old_three_outputs_and_patch_entry():
    calls = []
    outputs = ("select", ["owned"], "")

    def old_entry(file_id):
        calls.append(file_id)
        return outputs

    callback = file_selection_result(old_entry)
    stamp = {"viewVersion": 3}
    result = callback("owned", stamp)
    assert calls == ["owned"]
    assert result["outputs"] is outputs
    assert result["stamp"] is stamp
    assert result["file_id"] == "owned"
    assert callback.__name__ == old_entry.__name__
