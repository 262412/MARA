from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from gradio.helpers import special_args
from ktem.pages.chat import ChatPage
from ktem.pages.chat.source_scope import sync_graph_source_ids


def _chat_page() -> Any:
    return cast(Any, object.__new__(ChatPage))


def test_graph_scope_never_falls_back_to_selector_only_ids():
    assert (
        sync_graph_source_ids(
            ["victim-file"],
            {},
            {"victim-file": "Victim.pdf"},
        )
        == []
    )


def test_sidebar_empty_owner_scope_never_resolves_selector_only_victim():
    page = _chat_page()
    page._load_available_source_records = lambda _user_id: {}
    page._build_selector_source_map = lambda _choices: {"victim-file": "Victim.pdf"}
    page._resolve_source_file_path = lambda _file_id: (_ for _ in ()).throw(
        AssertionError("selector-only victim reached the path resolver")
    )

    rows = page._source_rows_for_sidebar(
        "attacker",
        [["Victim.pdf", "victim-file"]],
        ["victim-file"],
        "conversation-1",
        "",
    )

    assert rows == []


class _GraphScopeRuntime:
    def __init__(self) -> None:
        self.persist_calls: list[dict[str, Any]] = []

    def persist_graph_source_ids(self, conversation_id, source_ids, *, user_id):
        self.persist_calls.append(
            {
                "conversation_id": conversation_id,
                "source_ids": list(source_ids),
                "user_id": user_id,
            }
        )
        return list(source_ids)

    def load_graph_source_ids(self, _conversation_id, *, user_id):
        assert user_id == "attacker"
        return ["attacker-file", "victim-file"]


def _scoped_page() -> Any:
    page = _chat_page()
    page.docqa = _GraphScopeRuntime()
    page._resolve_persist_user_id = lambda _state_user, _request: "attacker"
    page._load_available_source_map = lambda user_id: (
        {"attacker-file": "Own.pdf"} if user_id == "attacker" else {}
    )
    return page


def test_persisted_graph_ids_are_intersected_with_request_owner_sources():
    page = _scoped_page()

    result = page.persist_conversation_source_scope(
        "conversation-1",
        "victim-state-user",
        ["attacker-file", "victim-file"],
        request=cast(Any, SimpleNamespace(username="attacker")),
    )

    assert result == ["attacker-file"]
    assert page.docqa.persist_calls == [
        {
            "conversation_id": "conversation-1",
            "source_ids": ["attacker-file"],
            "user_id": "attacker",
        }
    ]


def test_loaded_graph_ids_are_intersected_with_request_owner_sources():
    page = _scoped_page()

    result = page.load_conversation_graph_state(
        "conversation-1",
        "victim-state-user",
        request=cast(Any, SimpleNamespace(username="attacker")),
    )

    assert result == ["attacker-file"]


def test_scope_and_sidebar_callbacks_receive_injected_request():
    page = _scoped_page()
    request = cast(Any, SimpleNamespace(username="attacker"))
    callbacks: list[tuple[Any, list[Any]]] = [
        (
            page.sync_graph_source_ids_with_selector_choices,
            [["victim-file"], [["Victim.pdf", "victim-file"]], "victim-state"],
        ),
        (
            page.refresh_chat_file_list,
            [
                "conversation-1",
                "victim-state",
                [["Victim.pdf", "victim-file"]],
                ["victim-file"],
                ["victim-file"],
                "",
            ],
        ),
    ]

    for callback, component_inputs in callbacks:
        injected, _, _ = special_args(
            callback, inputs=list(component_inputs), request=request
        )
        assert injected == [*component_inputs, request]


def test_sidebar_refresh_uses_request_principal_not_user_state():
    page = _scoped_page()
    users: list[str] = []

    def source_rows(user_id, *_args):
        users.append(user_id)
        return []

    page._source_rows_for_sidebar = source_rows
    page._render_chat_file_list_html = lambda _rows, _selected: "list"
    page._render_corpus_summary_html = lambda _rows: "summary"

    outputs = page.refresh_chat_file_list(
        "conversation-1",
        "victim-state-user",
        [],
        [],
        [],
        "",
        request=cast(Any, SimpleNamespace(username="attacker")),
    )

    assert users == ["attacker"]
    assert len(outputs) == 4
