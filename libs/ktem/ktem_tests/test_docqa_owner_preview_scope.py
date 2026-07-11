from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
import pytest
from ktem.docqa.runtime import DocQARuntime


class _Reasoning:
    @staticmethod
    def get_info():
        return {"id": "simple"}

    @staticmethod
    def get_pipeline(_settings, _state, _retrievers):
        return SimpleNamespace()


class _Index:
    id = 9

    @staticmethod
    def get_retriever_pipelines(_settings, _user_id, _selected_input):
        return []


class _FileIndex:
    id = 9

    @staticmethod
    def resolve_selected_ids(_user_id, selected_input):
        return list(selected_input or [])


class _PreviewSpy:
    def __init__(self, page_text: str) -> None:
        self.page_text = page_text
        self.calls: list[tuple[str, tuple[Any, ...], Any]] = []

    def _record(self, name, *args, user_id=None):
        self.calls.append((name, args, user_id))

    def resolve_file_name(self, file_id, *, user_id=None):
        self._record("resolve_file_name", file_id, user_id=user_id)
        return "Owned.pdf"

    def resolve_selected_file(self, file_ids, *, user_id=None):
        self._record("resolve_selected_file", list(file_ids), user_id=user_id)
        return "owned-file", "Owned.pdf", "/owned/path"

    def resolve_file_path(self, file_id, *, user_id=None):
        self._record("resolve_file_path", file_id, user_id=user_id)
        return "/owned/path"

    def resolve_sources(self, file_ids, *, user_id=None, strict=True):
        self._record("resolve_sources", list(file_ids), strict, user_id=user_id)
        return [
            SimpleNamespace(file_id=file_id, name="Owned.pdf", path="/owned/path")
            for file_id in file_ids
        ]

    def get_page_context_text(
        self, file_id, file_name, page_number, *, user_id=None
    ) -> str:
        self._record(
            "get_page_context_text",
            file_id,
            file_name,
            page_number,
            user_id=user_id,
        )
        return self.page_text


def _runtime(monkeypatch, *, page_text: str) -> tuple[Any, _PreviewSpy]:
    monkeypatch.setattr(runtime_module, "reasonings", {"simple": _Reasoning})
    preview = _PreviewSpy(page_text)
    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._resolve_user_id = lambda _user_id=None: "attacker"
    runtime.load_settings = lambda _user_id=None: {"reasoning.use": "simple"}
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[_Index()]))
    runtime._web_search_cls = None
    runtime.file_index = _FileIndex()
    runtime._preview = preview
    return runtime, preview


def test_docqa_page_context_uses_resolved_user(monkeypatch):
    runtime, preview = _runtime(monkeypatch, page_text="Owned page text")

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="What is on this page?",
            user_id="victim-state-user",
            selected_inputs={9: ["owned-file"]},
            active_file_id="owned-file",
            page_number=2,
            qa_scope="page",
        )
    )

    assert prepared.active_file_name == "Owned.pdf"
    assert prepared.selected_text == "Owned page text"
    assert (
        "get_page_context_text",
        ("owned-file", "Owned.pdf", 2),
        "attacker",
    ) in preview.calls
    assert all(user_id == "attacker" for _name, _args, user_id in preview.calls)


def test_docqa_page_scope_empty_context_raises_typed_error(monkeypatch):
    runtime, _preview = _runtime(monkeypatch, page_text="")

    with pytest.raises(Exception) as caught:
        runtime._prepare_pipeline(
            runtime_module.DocQARequest(
                prompt="What is on this page?",
                selected_inputs={9: ["owned-file"]},
                active_file_id="owned-file",
                page_number=2,
                qa_scope="page",
            )
        )

    assert type(caught.value).__name__ == "PreviewContextError"
    assert "context_text_unavailable" in str(caught.value)


def test_runtime_load_session_facade_accepts_explicit_user(monkeypatch):
    runtime = cast(Any, object.__new__(DocQARuntime))
    calls: list[tuple[str, dict[str, Any]]] = []
    service = SimpleNamespace(
        load_session=lambda conversation_id, **kwargs: calls.append(
            (conversation_id, kwargs)
        )
    )
    monkeypatch.setattr(runtime, "_get_session_service", lambda: service)

    runtime.load_session("conversation-1", user_id="attacker")

    assert calls == [("conversation-1", {"user_id": "attacker"})]


def test_web_turn_loads_session_with_resolved_request_user(monkeypatch):
    runtime = cast(Any, object.__new__(DocQARuntime))
    loaded_users: list[Any] = []
    session = SimpleNamespace(conversation_id="conversation-1")
    runtime._resolve_user_id = lambda _user_id=None: "attacker"

    def load_session(_conversation_id, *, user_id=None):
        loaded_users.append(user_id)
        return session

    runtime.load_session = load_session
    runtime._resolve_selected_inputs = lambda _request, _session: {}
    runtime._prepare_pipeline = lambda _request: SimpleNamespace()
    monkeypatch.setattr(
        runtime_module._mara,
        "selected_ids",
        lambda _runtime, _user_id, _selected_inputs: [],
    )
    monkeypatch.setattr(
        runtime_module._turn,
        "build_turn_request",
        lambda request, *_args, **_kwargs: request,
    )

    runtime._prepare_turn_execution(
        runtime_module.DocQARequest(
            prompt="Question",
            conversation_id="conversation-1",
            user_id="victim-state-user",
        )
    )

    assert loaded_users == ["attacker"]
