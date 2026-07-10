from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class Marker:
    name: str


def marker(name: str) -> Marker:
    return Marker(name)


@dataclass(frozen=True)
class EventCall:
    node_id: int
    parent_id: int | None
    trigger: str
    verb: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    @property
    def params(self) -> dict[str, Any]:
        params = dict(self.kwargs)
        for name, value in zip(("fn", "inputs", "outputs"), self.args):
            params.setdefault(name, value)
        return params


class EventGraphSpy:
    def __init__(self) -> None:
        self.calls: list[EventCall] = []

    def root(
        self,
        trigger: str,
        verb: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> "ChainNodeSpy":
        return self._record(None, trigger, verb, args, kwargs)

    def child(
        self,
        parent_id: int,
        verb: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> "ChainNodeSpy":
        return self._record(parent_id, "chain", verb, args, kwargs)

    def _record(
        self,
        parent_id: int | None,
        trigger: str,
        verb: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> "ChainNodeSpy":
        node_id = len(self.calls)
        self.calls.append(
            EventCall(node_id, parent_id, trigger, verb, args, dict(kwargs))
        )
        return ChainNodeSpy(self, node_id)

    def call(self, node_id: int) -> EventCall:
        return self.calls[node_id]

    def roots(self, trigger: str | None = None) -> list[EventCall]:
        roots = [call for call in self.calls if call.parent_id is None]
        return [call for call in roots if trigger is None or call.trigger == trigger]


class ChainNodeSpy:
    def __init__(self, graph: EventGraphSpy, node_id: int) -> None:
        self.graph = graph
        self.node_id = node_id

    def then(self, *args: Any, **kwargs: Any) -> "ChainNodeSpy":
        return self.graph.child(self.node_id, "then", args, kwargs)

    def success(self, *args: Any, **kwargs: Any) -> "ChainNodeSpy":
        return self.graph.child(self.node_id, "success", args, kwargs)


class ComponentSpy:
    def __init__(self, graph: EventGraphSpy, name: str) -> None:
        self.graph = graph
        self.name = name

    def _event(self, verb: str, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self.graph.root(self.name, verb, args, kwargs)

    def click(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("click", *args, **kwargs)

    def select(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("select", *args, **kwargs)

    def submit(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("submit", *args, **kwargs)

    def upload(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("upload", *args, **kwargs)

    def change(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("change", *args, **kwargs)

    def tick(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("tick", *args, **kwargs)

    def load(self, *args: Any, **kwargs: Any) -> ChainNodeSpy:
        return self._event("load", *args, **kwargs)


def linear_chain(graph: EventGraphSpy, root: EventCall) -> list[EventCall]:
    chain = [root]
    while True:
        children = [call for call in graph.calls if call.parent_id == chain[-1].node_id]
        if not children:
            return chain
        if len(children) != 1:
            raise AssertionError(f"node {chain[-1].node_id} has {len(children)} children")
        chain.append(children[0])


def _build_app(graph: EventGraphSpy) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=marker("app.user_id"),
        settings_state=marker("app.settings_state"),
        f_user_management=True,
        subscribe_event=marker("app.subscribe_event"),
        app=ComponentSpy(graph, "app.load"),
    )


def _build_chat_control(graph: EventGraphSpy) -> SimpleNamespace:
    names = (
        "btn_chat_expand",
        "btn_demo_logout",
        "btn_new",
        "btn_del",
        "btn_del_conf",
        "btn_del_cnl",
        "btn_conversation_rn",
        "conversation_rn",
        "conversation",
    )
    controls: dict[str, Any] = {
        name: ComponentSpy(graph, f"chat_control.{name}") for name in names
    }
    controls.update(
        conversation_id=marker("chat_control.conversation_id"),
        cb_is_public=marker("chat_control.cb_is_public"),
        _new_delete=marker("chat_control._new_delete"),
        _delete_confirm=marker("chat_control._delete_confirm"),
        new_conv=marker("chat_control.new_conv"),
        select_conv=marker("chat_control.select_conv"),
        delete_conv=marker("chat_control.delete_conv"),
        rename_conv=marker("chat_control.rename_conv"),
        reload_conv=marker("chat_control.reload_conv"),
        logout_js="logout-js",
    )
    return SimpleNamespace(**controls)


def _build_chat_panel(graph: EventGraphSpy) -> SimpleNamespace:
    return SimpleNamespace(
        text_input=ComponentSpy(graph, "chat_panel.text_input"),
        chatbot=marker("chat_panel.chatbot"),
        page_number=ComponentSpy(graph, "chat_panel.page_number"),
        qa_scope=marker("chat_panel.qa_scope"),
        pdf_preview_src=marker("chat_panel.pdf_preview_src"),
        pdf_preview_notice=marker("chat_panel.pdf_preview_notice"),
        preview_refresh_timer=ComponentSpy(graph, "chat_panel.preview_refresh_timer"),
        prev_page_btn=ComponentSpy(graph, "chat_panel.prev_page_btn"),
        next_page_btn=ComponentSpy(graph, "chat_panel.next_page_btn"),
    )


def build_chat_page(graph: EventGraphSpy, index_count: int = 5) -> SimpleNamespace:
    page = SimpleNamespace()
    page._app = _build_app(graph)
    page.chat_control = _build_chat_control(graph)
    page.chat_panel = _build_chat_panel(graph)
    page._indices_input = [marker(f"indices[{index}]") for index in range(index_count)]
    page.page_preview = SimpleNamespace(
        cache_page_outputs=marker("page_preview.cache_page_outputs"),
        refresh_selected_file_preview=marker(
            "page_preview.refresh_selected_file_preview"
        ),
        on_selected_file_change=marker("page_preview.on_selected_file_change"),
        on_preview_tick=marker("page_preview.on_preview_tick"),
        on_prev_page=marker("page_preview.on_prev_page"),
        on_next_page=marker("page_preview.on_next_page"),
        on_page_set=marker("page_preview.on_page_set"),
    )
    page.paper_list = SimpleNamespace(accordion=marker("paper_list.accordion"))
    page.submit_msg = marker("page.submit_msg")
    page.chat_fn = marker("page.chat_fn")
    page.suggest_chat_conv = marker("page.suggest_chat_conv")
    page.check_and_suggest_name_conv = marker("page.check_and_suggest_name_conv")
    page.persist_data_source = marker("page.persist_data_source")
    page._json_to_plot = marker("page._json_to_plot")
    page.toggle_delete = marker("page.toggle_delete")
    page.render_latest_citations_card = marker("page.render_latest_citations_card")
    page.render_latest_reasoning_trace = marker("page.render_latest_reasoning_trace")
    page.refresh_page_context_view = marker("page.refresh_page_context_view")
    page.get_recommendations = marker("page.get_recommendations")
    _add_chat_markers(page)
    return page


def _add_chat_markers(page: SimpleNamespace) -> None:
    names = (
        "first_selector_choices _graph_source_ids _selected_page_text "
        "_selected_graph_context _last_question _command_state _reasoning_type "
        "model_type use_mindmap citation language state_chat _active_file_id "
        "_active_file_name state_plot_panel info_panel plot_panel answer_panel "
        "citations_panel reasoning_trace_panel _request_page_number _request_file_id "
        "_request_last_question _request_info_html _request_answer_html "
        "_request_chat_history _page_outputs_cache _conversation_renamed "
        "_preview_links followup_questions_ui followup_questions "
        "state_retrieval_history state_plot_history chat_settings _active_file_path "
        "_active_file_total_pages page_strip_search page_strip_file_summary "
        "page_thumbnail_strip page_metadata_strip related_papers _user_api_key "
        "_use_suggestion"
    ).split()
    for name in names:
        setattr(page, name, marker(f"page.{name}"))
    for name in (
        "docqa_controller_mode",
        "docqa_route_policy",
        "docqa_verification_mode",
        "docqa_planner_model",
    ):
        setattr(page, name, marker(f"page.{name}"))
