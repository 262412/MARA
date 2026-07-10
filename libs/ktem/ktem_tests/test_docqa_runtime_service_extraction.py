from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa._runtime_file_service import RuntimeFileService
from ktem.docqa._runtime_session_service import RuntimeSessionService
from ktem.docqa.runtime import DocQARuntime


class _ServiceSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return name

    def load_settings(self, *args, **kwargs):
        return self._record("load_settings", *args, **kwargs)

    def list_sessions(self, *args, **kwargs):
        return self._record("list_sessions", *args, **kwargs)

    def load_session(self, *args, **kwargs):
        return self._record("load_session", *args, **kwargs)

    def create_session(self, *args, **kwargs):
        return self._record("create_session", *args, **kwargs)

    def build_selected_mapping(self, *args, **kwargs):
        return self._record("build_selected_mapping", *args, **kwargs)

    def persist_conversation_state(self, *args, **kwargs):
        return self._record("persist_conversation_state", *args, **kwargs)

    def list_files(self, *args, **kwargs):
        return self._record("list_files", *args, **kwargs)

    def resolve_file_refs(self, *args, **kwargs):
        return self._record("resolve_file_refs", *args, **kwargs)

    def expand_zip_inputs(self, *args, **kwargs):
        return self._record("expand_zip_inputs", *args, **kwargs)

    def expand_index_inputs(self, *args, **kwargs):
        return self._record("expand_index_inputs", *args, **kwargs)

    def index_paths(self, *args, **kwargs):
        return self._record("index_paths", *args, **kwargs)

    def delete_files(self, *args, **kwargs):
        return self._record("delete_files", *args, **kwargs)


def _runtime() -> DocQARuntime:
    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._user_id = "user-1"
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    runtime.file_index = None
    return runtime


def test_runtime_session_facades_delegate_without_changing_arguments(monkeypatch):
    runtime = _runtime()
    service = _ServiceSpy()
    monkeypatch.setattr(runtime, "_get_session_service", lambda: service)

    assert runtime.load_settings("user-2") == "load_settings"
    assert runtime.list_sessions("user-2") == "list_sessions"
    assert runtime.load_session("conversation-1") == "load_session"
    assert runtime.create_session("Named", "user-2") == "create_session"
    assert (
        runtime._build_selected_mapping(
            {9: ["file-1"]},
            ["file-1"],
            "user-2",
            {"9": ["all", [], "user-2"]},
        )
        == "build_selected_mapping"
    )
    assert (
        runtime.persist_conversation_state(
            "conversation-1",
            "user-2",
            "refs",
            None,
            [],
            [],
            [("question", "answer")],
            {"app": {"regen": False}},
            ["file-1"],
            {9: ["file-1"]},
            ["file-1"],
            "web",
        )
        == "persist_conversation_state"
    )

    assert [call[0] for call in service.calls] == [
        "load_settings",
        "list_sessions",
        "load_session",
        "create_session",
        "build_selected_mapping",
        "persist_conversation_state",
    ]


def test_runtime_file_facades_delegate_without_changing_arguments(monkeypatch):
    runtime = _runtime()
    service = _ServiceSpy()
    monkeypatch.setattr(runtime, "_get_file_service", lambda: service)

    assert runtime.list_files("user-2") == "list_files"
    assert runtime.resolve_file_refs(["report"], "user-2") == "resolve_file_refs"
    assert runtime._expand_zip_inputs(["bundle.zip"]) == "expand_zip_inputs"
    assert runtime._expand_index_inputs(["folder"]) == "expand_index_inputs"
    assert runtime.index_paths(["report.pdf"], True, "user-2", {"x": 1}) == (
        "index_paths"
    )
    assert runtime.delete_files(["report"], "user-2") == "delete_files"

    assert [call[0] for call in service.calls] == [
        "list_files",
        "resolve_file_refs",
        "expand_zip_inputs",
        "expand_index_inputs",
        "index_paths",
        "delete_files",
    ]


def test_extracted_services_are_no_gradio_plain_python_boundaries():
    assert RuntimeSessionService.__module__ == "ktem.docqa._runtime_session_service"
    assert RuntimeFileService.__module__ == "ktem.docqa._runtime_file_service"
    assert "gradio" not in RuntimeSessionService.__module__
    assert "gradio" not in RuntimeFileService.__module__
