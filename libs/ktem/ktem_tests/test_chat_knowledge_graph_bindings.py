from types import SimpleNamespace

from ktem.pages.chat.chat_knowledge_graph_bindings import (
    bind_knowledge_graph_events,
    subscribe_public_knowledge_graph_events,
)


class _FakeChain:
    def __init__(self, trigger_name, kwargs):
        self.trigger_name = trigger_name
        self.steps = [(trigger_name, kwargs)]

    def then(self, **kwargs):
        self.steps.append(("then", kwargs))
        return self


class _FakeTrigger:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def change(self, **kwargs):
        chain = _FakeChain("change", kwargs)
        self.calls.append(chain)
        return chain

    def click(self, **kwargs):
        chain = _FakeChain("click", kwargs)
        self.calls.append(chain)
        return chain

    def select(self, **kwargs):
        chain = _FakeChain("select", kwargs)
        self.calls.append(chain)
        return chain


class _FakeApp:
    def __init__(self):
        self.user_id = "user-id"
        self._tabs = {"chat-tab": _FakeTrigger("chat-tab")}
        self.subscriptions = []

    def subscribe_event(self, name, definition):
        self.subscriptions.append((name, definition))


def _make_page():
    app = _FakeApp()
    chat_file_filter = _FakeTrigger("chat_file_filter")
    selector_input = _FakeTrigger("selector_input")
    chat_file_click = _FakeTrigger("chat_file_click")
    selector_choices = _FakeTrigger("selector_choices")
    conversation_id = _FakeTrigger("conversation_id")

    page = SimpleNamespace(
        _app=app,
        knowledge_graph=object(),
        file_index=SimpleNamespace(id="index-1"),
        _indices_input=["selector-group", selector_input],
        _graph_source_ids="graph-source-ids",
        _active_file_id="active-file-id",
        state_plot_panel="state-plot-panel",
        plot_panel="plot-panel",
        chat_file_rows="chat-file-rows",
        chat_file_list="chat-file-list",
        chat_selected_file="chat-selected-file",
        workbench_file_summary="workbench-file-summary",
        chat_file_filter=chat_file_filter,
        _chat_file_click=chat_file_click,
        first_selector_choices=selector_choices,
        refresh_chat_file_list=object(),
        show_knowledge_graph_loading=object(),
        refresh_knowledge_graph=object(),
        generate_knowledge_graph=object(),
        select_chat_file=object(),
        sync_graph_source_ids_with_selector_choices=object(),
        persist_conversation_source_scope=object(),
        load_conversation_graph_state=object(),
        chat_control=SimpleNamespace(conversation_id=conversation_id),
    )
    return page


def test_bind_knowledge_graph_events_wires_source_scope_chains():
    page = _make_page()

    bind_knowledge_graph_events(page)

    selector_change_chain = page._indices_input[1].calls[0]
    assert selector_change_chain.trigger_name == "change"
    assert selector_change_chain.steps[0][1]["fn"] is page.refresh_chat_file_list
    assert len(selector_change_chain.steps) == 1

    selector_scope_chain = page.first_selector_choices.calls[0]
    assert [step[1]["fn"] for step in selector_scope_chain.steps] == [
        page.sync_graph_source_ids_with_selector_choices,
        page.persist_conversation_source_scope,
        page.refresh_chat_file_list,
    ]

    conversation_chain = page.chat_control.conversation_id.calls[0]
    assert [step[1]["fn"] for step in conversation_chain.steps] == [
        page.load_conversation_graph_state,
        page.sync_graph_source_ids_with_selector_choices,
        page.persist_conversation_source_scope,
        page.refresh_chat_file_list,
    ]

    assert not hasattr(page, "knowledge_graph_refresh")


def test_subscribe_public_knowledge_graph_events_registers_source_scope_pipeline():
    page = _make_page()
    page.generate_knowledge_graph = object()

    subscribe_public_knowledge_graph_events(page)

    assert len(page._app.subscriptions) == 3
    names = {name for name, _ in page._app.subscriptions}
    assert names == {"onFileIndexindex-1Changed"}
    assert [definition["fn"] for _, definition in page._app.subscriptions] == [
        page.sync_graph_source_ids_with_selector_choices,
        page.persist_conversation_source_scope,
        page.refresh_chat_file_list,
    ]
