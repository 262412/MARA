from __future__ import annotations

import logging

from ktem.index.file._chat_upload_events import (
    full_upload_ports,
    quick_file_upload_ports,
    quick_url_upload_ports,
    register_quick_upload_events,
    register_upload_events,
)
from ktem.index.file._events import (
    register_quick_upload_events as reexported_quick_upload_events,
    register_upload_events as reexported_upload_events,
)

from .event_chain_spy import EventGraphSpy, linear_chain
from .file_index_event_spy import build_upload_page


def _fn_name(call):
    fn = call.params.get("fn")
    return getattr(fn, "name", getattr(fn, "__name__", None))


def test_quick_upload_ports_preserve_scalar_list_and_none_shapes():
    page = build_upload_page(EventGraphSpy())

    file_ports = quick_file_upload_ports(page)
    url_ports = quick_url_upload_ports(page)

    assert file_ports.index.inputs[0] is page._app.chat_page.quick_file_upload
    assert url_ports.index.inputs[0] is page._app.chat_page.quick_urls
    assert isinstance(file_ports.index.gradio_inputs, list)
    assert file_ports.index.gradio_outputs is page.quick_upload_state
    assert file_ports.selector_copy.gradio_inputs is page.quick_upload_state
    assert (
        file_ports.selector_copy.gradio_outputs is page._app.chat_page._indices_input[1]
    )
    assert file_ports.focus.gradio_inputs is None
    assert file_ports.focus.gradio_outputs is None
    assert file_ports.reset.outputs == (
        page._app.chat_page.quick_file_upload,
        page._app.chat_page._indices_input[0],
    )
    assert reexported_quick_upload_events is register_quick_upload_events
    assert reexported_upload_events is register_upload_events


def test_standard_quick_upload_chains_keep_exact_verbs_functions_and_parents():
    graph = EventGraphSpy()
    page = build_upload_page(graph)

    register_quick_upload_events(page, demo_mode=False, chat_input_focus_js="focus-js")

    assert [root.trigger for root in graph.roots()] == [
        "chat.quick_file_upload",
        "chat.quick_urls",
    ]
    for trigger, index_fn in (
        ("chat.quick_file_upload", "page.index_fn_file_with_default_loaders"),
        ("chat.quick_urls", "page.index_fn_url_with_default_loaders"),
    ):
        chain = linear_chain(graph, graph.roots(trigger)[0])
        assert [call.verb for call in chain] == [
            "upload" if trigger.endswith("file_upload") else "submit",
            "then",
            "success",
            "then",
            "then",
            "success",
            "then",
            "success",
            "success",
            "then",
            "then",
            "then",
        ]
        assert [_fn_name(call) for call in chain] == [
            "_quick_upload_waiting_update",
            index_fn,
            "<lambda>",
            "public.0",
            "public.1",
            "chat.merge_graph_source_ids",
            "chat.refresh_chat_file_list",
            "<lambda>",
            "chat.persist_conversation_source_scope",
            "<lambda>",
            "page.list_file",
            "<lambda>",
        ]
        assert [call.parent_id for call in chain[1:]] == [
            call.node_id for call in chain[:-1]
        ]
        assert chain[3].params["inputs"] is page._app.get_event("unused")[0]["inputs"]
        assert chain[7].params["inputs"] is page.quick_upload_state
        assert chain[-1].params["js"] == "focus-js"


def test_demo_quick_upload_omits_file_trigger_and_file_list_refresh_only():
    graph = EventGraphSpy()
    page = build_upload_page(graph)

    register_quick_upload_events(page, demo_mode=True, chat_input_focus_js="focus-js")

    assert [root.trigger for root in graph.roots()] == ["chat.quick_urls"]
    chain = linear_chain(graph, graph.roots("chat.quick_urls")[0])
    assert "page.list_file" not in [_fn_name(call) for call in chain]
    assert _fn_name(chain[-2]) == "<lambda>"
    assert chain[-1].params["js"] == "focus-js"


def test_full_upload_clear_files_is_independent_child_of_clear_url():
    graph = EventGraphSpy()
    page = build_upload_page(graph)

    register_upload_events(page)

    root = graph.roots("page.upload_button")[0]
    snapshot = next(call for call in graph.calls if call.parent_id == root.node_id)
    index = next(call for call in graph.calls if call.parent_id == snapshot.node_id)
    clear_url = next(call for call in graph.calls if call.parent_id == index.node_id)
    branches = [call for call in graph.calls if call.parent_id == clear_url.node_id]
    assert [(call.verb, _fn_name(call)) for call in branches] == [
        ("then", "page.collect_new_source_ids"),
        ("success", "<lambda>"),
    ]
    collect, clear_files = branches
    assert clear_files.params["outputs"] == [page.files]
    graph_tail = [collect]
    while True:
        children = [
            call for call in graph.calls if call.parent_id == graph_tail[-1].node_id
        ]
        if not children:
            break
        assert len(children) == 1
        graph_tail.append(children[0])
    assert [_fn_name(call) for call in graph_tail] == [
        "page.collect_new_source_ids",
        "page.list_file",
        "public.0",
        "public.1",
        "chat.merge_graph_source_ids",
        "chat.persist_conversation_source_scope",
        "chat.refresh_chat_file_list",
    ]
    assert clear_files.parent_id == clear_url.node_id
    assert clear_files.parent_id != graph_tail[-1].node_id
    assert full_upload_ports(page).clear_files.outputs == (page.files,)


def test_full_upload_does_not_read_chat_graph_ports_when_refresh_is_disabled():
    graph = EventGraphSpy()
    page = build_upload_page(graph)
    page._index.id = 2
    del page._app.chat_page._graph_source_ids
    del page._app.chat_page.first_selector_choices

    register_upload_events(page)

    graph_tail_functions = [_fn_name(call) for call in graph.calls]
    assert "chat.merge_graph_source_ids" not in graph_tail_functions
    assert "chat.persist_conversation_source_scope" not in graph_tail_functions
    assert "chat.refresh_chat_file_list" not in graph_tail_functions


def test_quick_upload_registration_logs_actionable_stage_and_remains_resilient(
    caplog,
):
    page = build_upload_page(EventGraphSpy())
    page._app.chat_page.quick_file_upload = None

    with caplog.at_level(logging.ERROR):
        register_quick_upload_events(
            page, demo_mode=False, chat_input_focus_js="focus-js"
        )

    assert "index_id=1" in caplog.text
    assert "demo_mode=False" in caplog.text
    assert "stage=quick-file-upload" in caplog.text
