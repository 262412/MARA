from __future__ import annotations

from types import SimpleNamespace

from .event_chain_spy import ComponentSpy, EventGraphSpy, marker


def build_upload_page(graph: EventGraphSpy, *, public_event_count: int = 2):
    page = SimpleNamespace()
    page._index = SimpleNamespace(id=1)
    page.quick_upload_state = marker("page.quick_upload_state")
    page.upload_button = ComponentSpy(graph, "page.upload_button")
    page.btn_close_upload_progress_panel = ComponentSpy(
        graph, "page.btn_close_upload_progress_panel"
    )
    _add_upload_page_ports(page)
    chat_page = _build_chat_page(graph)
    public_events = [
        {
            "fn": marker(f"public.{index}"),
            "inputs": marker(f"public.inputs.{index}") if index == 0 else None,
            "outputs": None,
        }
        for index in range(public_event_count)
    ]
    page._app = SimpleNamespace(
        user_id=marker("app.user_id"),
        settings_state=marker("app.settings_state"),
        chat_page=chat_page,
        get_event=lambda _name: list(public_events),
    )
    return page


def _add_upload_page_ports(page: SimpleNamespace) -> None:
    names = (
        "upload_progress_panel upload_before_source_ids upload_result upload_info "
        "urls files reindex upload_new_source_ids file_list_state file_list filter"
    ).split()
    for name in names:
        setattr(page, name, marker(f"page.{name}"))
    functions = (
        "snapshot_source_ids index_fn collect_new_source_ids list_file "
        "index_fn_file_with_default_loaders index_fn_url_with_default_loaders"
    ).split()
    for name in functions:
        setattr(page, name, marker(f"page.{name}"))


def _build_chat_page(graph: EventGraphSpy) -> SimpleNamespace:
    return SimpleNamespace(
        quick_file_upload=ComponentSpy(graph, "chat.quick_file_upload"),
        quick_file_upload_status=marker("chat.quick_file_upload_status"),
        quick_urls=ComponentSpy(graph, "chat.quick_urls"),
        _indices_input=[
            marker("chat.indices.mode"),
            marker("chat.indices.files"),
            marker("chat.indices.user"),
        ],
        _graph_source_ids=marker("chat.graph_source_ids"),
        first_selector_choices=marker("chat.first_selector_choices"),
        chat_file_filter=marker("chat.chat_file_filter"),
        chat_file_rows=marker("chat.chat_file_rows"),
        chat_file_list=marker("chat.chat_file_list"),
        chat_selected_file=marker("chat.chat_selected_file"),
        workbench_file_summary=marker("chat.workbench_file_summary"),
        knowledge_graph=marker("chat.knowledge_graph"),
        chat_control=SimpleNamespace(conversation_id=marker("chat.conversation_id")),
        merge_graph_source_ids=marker("chat.merge_graph_source_ids"),
        refresh_chat_file_list=marker("chat.refresh_chat_file_list"),
        persist_conversation_source_scope=marker(
            "chat.persist_conversation_source_scope"
        ),
    )
