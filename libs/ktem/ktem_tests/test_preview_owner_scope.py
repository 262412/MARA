from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import pytest
from gradio.helpers import special_args
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base


@pytest.fixture(autouse=True)
def _temporary_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))


@pytest.fixture
def owned_preview_app(tmp_path):
    base = declarative_base()

    class Source(base):  # type: ignore[valid-type,misc]
        __tablename__ = "task_12c2_preview_source"
        id = Column(String, primary_key=True)
        name = Column(String)
        path = Column(String)
        size = Column(Integer, default=0)
        date_created = Column(DateTime)
        user = Column(String)

    class Index(base):  # type: ignore[valid-type,misc]
        __tablename__ = "task_12c2_preview_index"
        id = Column(Integer, primary_key=True, autoincrement=True)
        source_id = Column(String)
        target_id = Column(String)
        relation_type = Column(String)

    db_engine = create_engine("sqlite://")
    base.metadata.create_all(db_engine)
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "attacker-doc").write_text("attacker", encoding="utf-8")
    (storage / "victim-doc").write_text("victim secret", encoding="utf-8")

    with Session(db_engine) as session:
        session.add_all(
            [
                Source(
                    id="attacker-file",
                    name="attacker.docx",
                    path="attacker-doc",
                    size=8,
                    user="attacker",
                ),
                Source(
                    id="victim-file",
                    name="victim.docx",
                    path="victim-doc",
                    size=13,
                    user="victim",
                ),
            ]
        )
        session.commit()

    index = SimpleNamespace(
        id=1,
        config={"private": True},
        _resources={
            "Source": Source,
            "Index": Index,
            "FileStoragePath": storage,
        },
    )
    app = SimpleNamespace(
        f_user_management=True,
        index_manager=SimpleNamespace(indices=[index]),
    )
    return app, db_engine, storage


def _assert_access_error(caught: pytest.ExceptionInfo[Exception]) -> None:
    assert type(caught.value).__name__ == "PreviewAccessError"
    assert "source_unavailable" in str(caught.value)
    assert "victim-doc" not in str(caught.value)


def test_preview_service_owner_boundary_is_non_disclosing(owned_preview_app):
    app, db_engine, storage = owned_preview_app
    context = importlib.import_module("ktem.preview.context")
    service_module = importlib.import_module("ktem.preview.service")
    access = context.PreviewAccess(user_id="attacker", owner_required=True)
    service = service_module.PreviewService(app, engine=db_engine)

    own = service.resolve_source("attacker-file", access=access)
    assert own.file_id == "attacker-file"
    assert own.name == "attacker.docx"
    assert own.path == (storage / "attacker-doc").resolve()
    assert own.owner == "attacker"

    messages = []
    for file_id in ("victim-file", "unknown-file"):
        with pytest.raises(Exception) as caught:
            service.resolve_source(file_id, access=access)
        _assert_access_error(caught)
        messages.append(str(caught.value))
    assert messages[0] == messages[1]


def test_preview_service_strict_batch_rejects_before_consumer_reads(owned_preview_app):
    app, db_engine, _storage = owned_preview_app
    context = importlib.import_module("ktem.preview.context")
    service_module = importlib.import_module("ktem.preview.service")
    service = service_module.PreviewService(app, engine=db_engine)
    access = context.PreviewAccess(user_id="attacker", owner_required=True)

    with pytest.raises(Exception) as caught:
        service.resolve_sources(
            ["attacker-file", "victim-file"], access=access, strict=True
        )
    _assert_access_error(caught)


def _managed_preview_controller(monkeypatch, owned_preview_app):
    import ktem.pages.chat.page_preview as preview_module
    import ktem.pages.chat.page_preview_callbacks as callback_module
    import ktem.pages.chat.page_preview_resolver as resolver_module

    app, db_engine, storage = owned_preview_app
    monkeypatch.setattr(resolver_module, "engine", db_engine)
    monkeypatch.setattr(callback_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        callback_module,
        "resolve_request_user_id",
        lambda _request, *, auth_mode: "attacker",
        raising=False,
    )
    controller = preview_module.ChatPagePreviewController(app)
    calls: list[tuple[Any, ...]] = []

    def build_payload(*args):
        calls.append(args)
        return 1, 1, "preview", "notice"

    monkeypatch.setattr(controller, "_build_preview_payload", build_payload)
    request = SimpleNamespace(username="attacker", session_hash="session-a")
    return controller, request, calls, storage


def test_selected_preview_rejects_victim_file_for_request_user(
    monkeypatch, owned_preview_app
):
    controller, request, calls, _storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )

    with pytest.raises(Exception) as caught:
        controller.on_selected_file_change(
            [], ["victim-file"], {}, request=cast(Any, request)
        )

    _assert_access_error(caught)
    assert calls == []


def test_navigation_re_resolves_id_and_ignores_tampered_path_state(
    monkeypatch, owned_preview_app
):
    controller, request, calls, storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )

    outputs = controller.on_next_page(
        1,
        "attacker-file",
        str(storage / "victim-doc"),
        {},
        1,
        request=cast(Any, request),
    )

    assert len(outputs) == 10
    assert calls[0][0:3] == (
        "attacker-file",
        "attacker.docx",
        str(storage / "attacker-doc"),
    )


def test_navigation_rejects_victim_id_before_using_path_state(
    monkeypatch, owned_preview_app
):
    controller, request, calls, storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )

    with pytest.raises(Exception) as caught:
        controller.on_next_page(
            1,
            "victim-file",
            str(storage / "attacker-doc"),
            {},
            1,
            request=cast(Any, request),
        )

    _assert_access_error(caught)
    assert calls == []


def test_restore_refresh_rejects_victim_file_for_request_user(
    monkeypatch, owned_preview_app
):
    controller, request, calls, _storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )

    with pytest.raises(Exception) as caught:
        controller.refresh_selected_file_preview(
            [], ["victim-file"], 1, 1, request=cast(Any, request)
        )

    _assert_access_error(caught)
    assert calls == []


def test_preview_timer_re_resolves_id_and_ignores_tampered_state(
    monkeypatch, owned_preview_app
):
    controller, request, calls, storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )
    controller._get_office_job_status = lambda _path: "pending"

    outputs = controller.on_preview_tick(
        "attacker-file",
        "victim.pdf",
        str(storage / "victim-doc"),
        1,
        1,
        "old-preview",
        "old-notice",
        request=cast(Any, request),
    )

    assert len(outputs) == 4
    assert calls[0][0:3] == (
        "attacker-file",
        "attacker.docx",
        str(storage / "attacker-doc"),
    )


def test_preview_timer_rejects_victim_id_before_extension_short_circuit(
    monkeypatch, owned_preview_app
):
    controller, request, calls, storage = _managed_preview_controller(
        monkeypatch, owned_preview_app
    )

    with pytest.raises(Exception) as caught:
        controller.on_preview_tick(
            "victim-file",
            "harmless.pdf",
            str(storage / "attacker-doc"),
            1,
            1,
            "old-preview",
            "old-notice",
            request=cast(Any, request),
        )

    _assert_access_error(caught)
    assert calls == []


def test_preview_callbacks_receive_exact_injected_gradio_request(owned_preview_app):
    from ktem.pages.chat.page_preview import ChatPagePreviewController

    app, _db_engine, _storage = owned_preview_app
    controller = ChatPagePreviewController(app)
    request = cast(Any, SimpleNamespace(username="attacker", session_hash="session-a"))
    cases = [
        (controller.on_selected_file_change, [[], ["file"], {}]),
        (controller.on_prev_page, [1, "file", "/state", {}, 1]),
        (controller.on_next_page, [1, "file", "/state", {}, 1]),
        (controller.on_page_set, [1, "file", "/state", {}, 1]),
        (controller.refresh_selected_file_preview, [[], ["file"], 1, 1]),
        (
            controller.on_preview_tick,
            ["file", "file.docx", "/state", 1, 1, "preview", "notice"],
        ),
    ]

    for callback, component_inputs in cases:
        injected, _, _ = special_args(
            callback, inputs=list(component_inputs), request=request
        )
        assert injected == [*component_inputs, request]


def test_preview_direct_call_abi_keeps_shapes(monkeypatch, owned_preview_app):
    import ktem.pages.chat.page_preview as preview_module
    import ktem.pages.chat.page_preview_callbacks as callback_module
    import ktem.pages.chat.page_preview_resolver as resolver_module

    app, db_engine, storage = owned_preview_app
    app.f_user_management = False
    app.index_manager.indices[0].config = {"private": False}
    monkeypatch.setattr(resolver_module, "engine", db_engine)
    monkeypatch.setattr(callback_module.flowsettings, "MARA_AUTH_MODE", "local")
    controller = preview_module.ChatPagePreviewController(app)
    monkeypatch.setattr(
        controller,
        "_build_preview_payload",
        lambda *_args: (1, 1, "preview", "notice"),
    )
    monkeypatch.setattr(controller, "_get_office_job_status", lambda _path: "pending")

    selected = controller.on_selected_file_change([], ["attacker-file"], {})
    navigation = controller.on_next_page(
        1, "attacker-file", str(storage / "attacker-doc"), {}, 1
    )
    refresh = controller.refresh_selected_file_preview([], ["attacker-file"], 1, 1)
    timer_7 = controller.on_preview_tick(
        "attacker-file",
        "attacker.docx",
        str(storage / "attacker-doc"),
        1,
        1,
        "old",
        "notice",
    )
    timer_8 = controller.on_preview_tick(
        2.0,
        "attacker-file",
        "attacker.docx",
        str(storage / "attacker-doc"),
        1,
        1,
        "old",
        "notice",
    )

    assert len(selected) == 14
    assert len(navigation) == 10
    assert len(refresh) == 7
    assert len(timer_7) == len(timer_8) == 4
    assert len(controller.clear_page_outputs()) == 6
    assert controller.on_preview_tick.__annotations__["request"] is gr.Request
