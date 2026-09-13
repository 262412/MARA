"""Fixed expectations for the original control callbacks, before extraction."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import pytest
from ktem.pages.chat import control as module


def control_case(monkeypatch, *, indices=(), info=None, identity="owner", history=()):
    control: Any = object.__new__(module.ConversationControl)
    control._app = SimpleNamespace(index_manager=SimpleNamespace(indices=indices))
    calls = []

    def operation(name, result):
        def call(*args, **kwargs):
            calls.append((name, args, kwargs))
            if isinstance(result, Exception):
                raise result
            return result

        return call

    service = SimpleNamespace(
        load_session=operation("load", info),
        create_session=operation("create", SimpleNamespace(conversation_id="created")),
    )
    mutations = SimpleNamespace(delete_session=operation("delete", None))
    control._resolve_user_id = operation("identity", identity)
    control._get_session_service = operation("service", service)
    control._get_mutation_service = operation("mutations", mutations)
    control._load_chat_history = operation("history", history)
    monkeypatch.setattr(module.gr, "Warning", operation("warning", None))
    monkeypatch.setattr(module.logger, "warning", operation("log", None))
    return control, calls, service, mutations, operation


def session_info(**changes):
    fields = dict(
        conversation_id="loaded",
        name="Original name",
        user_id="owner",
        is_public=True,
        selected_mapping={"5": ["chosen"], "7": ["select", ["document"], "owner"]},
        messages=[("projected", "not the original source")],
        data_source={"messages": [["raw question", "raw answer"]]},
        retrieval_messages=["older reference", "last reference"],
        plot_history=[{"older": 1}, {"last": 2}],
        state={"nested": {"value": 1}},
    )
    fields.update(changes)
    return SimpleNamespace(**fields)


def selectors():
    return [
        SimpleNamespace(id="ignored", selector=None),
        SimpleNamespace(id=5, selector=0, default_selector=["default single"]),
        SimpleNamespace(id=7, selector=(1, 2, 3), default_selector=["all", [], ""]),
        SimpleNamespace(id=8, selector="unsupported"),
    ]


def test_control_is_loaded_from_this_checkout():
    assert Path(module.__file__).resolve() == (
        Path(__file__).resolve().parents[1] / "ktem/pages/chat/control.py"
    )
    assert gr.__version__ == "4.39.0"


def test_new_orders_identity_create_and_refresh_once(monkeypatch):
    history = [("Older", "old"), ("Created", "created")]
    control, calls, *_ = control_case(monkeypatch, history=history)
    request = object()
    assert control.new_conv("claimed", request) == (
        "created",
        {"value": "created", "choices": history, "__type__": "update"},
    )
    assert calls == [
        ("identity", ("claimed", request), {}),
        ("service", ("owner",), {}),
        ("create", (), {"user_id": "owner"}),
        ("history", ("owner",), {}),
    ]


@pytest.mark.parametrize("method,args", [("new_conv", ()), ("delete_conv", ("id",))])
def test_missing_identity_warns_without_mutation_or_list_refresh(
    monkeypatch, method, args
):
    control, calls, *_ = control_case(monkeypatch, identity=None)
    assert getattr(control, method)(*args, "claimed") == (None, {"__type__": "update"})
    assert [c[0] for c in calls] == ["identity", "warning"]
    assert calls[1][1] == ("Please sign in first (Settings → User Settings)",)


@pytest.mark.parametrize("conversation_id", [None, "", 0])
def test_delete_without_selection_precedes_identity(monkeypatch, conversation_id):
    control, calls, *_ = control_case(monkeypatch, identity=ValueError("identity"))
    assert control.delete_conv(conversation_id, "claimed") == (
        None,
        {"__type__": "update"},
    )
    assert calls == [("warning", ("No conversation selected.",), {})]


@pytest.mark.parametrize(
    "history,chosen", [([], None), ([("First", "one"), ("Next", "two")], "one")]
)
def test_delete_chooses_original_first_item_or_explicit_empty(
    monkeypatch, history, chosen
):
    control, calls, *_ = control_case(monkeypatch, history=history)
    assert control.delete_conv("old", "claimed") == (
        chosen,
        {"value": chosen, "choices": history, "__type__": "update"},
    )
    assert calls == [
        ("identity", ("claimed", module._REQUEST), {}),
        ("mutations", ("owner",), {}),
        ("delete", ("old", "owner"), {}),
        ("history", ("owner",), {}),
    ]


@pytest.mark.parametrize(
    "error", [PermissionError("owner scope"), RuntimeError("storage")]
)
def test_delete_failure_keeps_original_exception_boundary(monkeypatch, error):
    control, calls, _, mutation, operation = control_case(monkeypatch)
    mutation.delete_session = operation("delete", error)
    with pytest.raises(
        gr.Error if isinstance(error, PermissionError) else RuntimeError
    ) as caught:
        control.delete_conv("old", "owner")
    if isinstance(error, PermissionError):
        assert caught.value.__cause__ is error
        assert caught.value.message == "owner scope"
    else:
        assert caught.value is error
    assert [c[0] for c in calls] == ["identity", "mutations", "delete"]


@pytest.mark.parametrize(
    "method,args",
    [("new_conv", ()), ("select_conv", ("id",)), ("delete_conv", ("id",))],
)
def test_identity_exception_is_not_caught_or_replaced(monkeypatch, method, args):
    error = ValueError("identity failed")
    control, calls, *_ = control_case(monkeypatch, identity=error)
    with pytest.raises(ValueError) as caught:
        getattr(control, method)(*args, "claimed")
    assert caught.value is error
    assert [c[0] for c in calls] == ["identity"]


def test_create_and_refresh_errors_short_circuit_at_the_original_position(monkeypatch):
    control, calls, service, _, operation = control_case(monkeypatch)
    error = ValueError("create failed")
    service.create_session = operation("create", error)
    with pytest.raises(ValueError) as caught:
        control.new_conv("owner")
    assert caught.value is error
    assert [c[0] for c in calls] == ["identity", "service", "create"]
    calls.clear()
    service.create_session = operation("create", SimpleNamespace(conversation_id="new"))
    control._load_chat_history = operation("history", error)
    with pytest.raises(ValueError) as caught:
        control.new_conv("owner")
    assert caught.value is error
    assert [c[0] for c in calls] == ["identity", "service", "create", "history"]


@pytest.mark.parametrize("owner", [True, False])
def test_select_preserves_sources_references_slots_and_private_selection(
    monkeypatch, owner
):
    info = session_info()
    layout = selectors()
    control, calls, *_ = control_case(
        monkeypatch, indices=layout, info=info, identity="owner" if owner else "viewer"
    )
    result = control.select_conv("requested", "claimed")
    assert len(result) == 15  # 11 fixed outputs + 1 scalar + 3 tuple outputs.
    assert result[:3] == ("loaded", "loaded", "Original name")
    assert result[3] is info.data_source["messages"]
    assert result[4] == [[s] for s in module.ChatSuggestion.CHAT_SAMPLES]
    assert result[5] == "last reference"
    assert result[6] is info.plot_history[-1]
    assert result[7] is info.retrieval_messages
    assert result[8] is info.plot_history
    assert result[9] is True
    assert result[10] is info.state
    assert result[11] is (
        info.selected_mapping["5"] if owner else layout[1].default_selector
    )
    assert result[12:] == tuple(
        info.selected_mapping["7"] if owner else layout[2].default_selector
    )
    assert result[13] is (
        info.selected_mapping["7"][1] if owner else layout[2].default_selector[1]
    )
    assert [c[0] for c in calls] == ["identity", "service", "load"]


@pytest.mark.parametrize("suggestions", [None, [], [["custom"]]])
def test_select_preserves_explicit_suggestions_and_empty_histories(
    monkeypatch, suggestions
):
    info = session_info(
        data_source={"chat_suggestions": suggestions},
        retrieval_messages=[],
        plot_history=[],
        state=None,
    )
    control, *_ = control_case(monkeypatch, info=info)
    result = control.select_conv("id", "owner")
    assert result[3] == []
    assert result[4] is suggestions
    assert result[5] == "<h5><b>No evidence found.</b></h5>"
    assert result[6] is None and result[10] is None
    assert result[7] is info.retrieval_messages and result[8] is info.plot_history


@pytest.mark.parametrize(
    "info", [None, ValueError("read failed"), session_info(data_source=None)]
)
def test_select_load_projection_failures_log_then_clear(monkeypatch, info):
    layout = selectors()
    control, calls, *_ = control_case(monkeypatch, indices=layout, info=info)
    result = control.select_conv("requested", "owner")
    assert result[:11] == (
        "",
        "",
        "",
        [],
        [[s] for s in module.ChatSuggestion.CHAT_SAMPLES],
        "",
        None,
        [],
        [],
        False,
        module.STATE,
    )
    assert result[10] is module.STATE
    assert result[11:] == (layout[1].default_selector, *layout[2].default_selector)
    assert [c[0] for c in calls] == ["identity", "service", "load", "log"]
    assert calls[-1][1][0] == "Conversation selection failed: %s"
    if isinstance(info, Exception):
        assert calls[-1][1][1] is info


def test_selector_errors_are_outside_selection_catch_and_default_is_eager(monkeypatch):
    error = RuntimeError("selector failed")

    class Index:
        selector = 0
        id = 5

        @property
        def default_selector(self):
            raise error

    control, calls, *_ = control_case(
        monkeypatch, indices=[Index()], info=session_info()
    )
    with pytest.raises(RuntimeError) as caught:
        control.select_conv("id", "owner")
    assert caught.value is error
    assert [c[0] for c in calls] == ["identity", "service", "load"]


def test_clear_has_no_operations_and_keeps_default_references_and_old_patch(
    monkeypatch,
):
    layout = selectors()
    del layout[1].id  # Clear never needs a persisted index ID.
    del layout[2].id
    control, calls, *_ = control_case(monkeypatch, indices=layout)
    result = control.clear_conv()
    assert result[:11] == (
        "",
        "",
        "",
        [],
        [[s] for s in module.ChatSuggestion.CHAT_SAMPLES],
        "",
        None,
        [],
        [],
        False,
        module.STATE,
    )
    assert result[10] is module.STATE
    assert result[11] is layout[1].default_selector
    assert result[13] is layout[2].default_selector[1]
    assert calls == []
    assert control.clear_conv()[4] is not result[4]
    sentinel = object()
    monkeypatch.setattr(module, "_empty_conversation_state", lambda app: sentinel)
    assert control.clear_conv() is sentinel


def test_reload_uses_public_history_override_and_explicit_clear(monkeypatch):
    control, calls, _, _, operation = control_case(monkeypatch)
    history = [("First", "one")]
    control.load_chat_history = operation("public override", history)
    assert control.reload_conv("claimed") == {
        "value": None,
        "choices": history,
        "__type__": "update",
    }
    assert calls == [("public override", ("claimed", module._REQUEST), {})]


@pytest.fixture
def authenticated_rows(monkeypatch):
    from ktem.db.models import Conversation, User, engine
    from sqlmodel import Session

    owner = User(
        username="control-owner",
        username_lower="control-owner",
        password="unused-fixture",
    )
    viewer = User(
        username="control-viewer",
        username_lower="control-viewer",
        password="unused-fixture",
    )
    private = Conversation(user=owner.id, name="Private")
    public = Conversation(user=owner.id, name="Public", is_public=True)
    public.data_source = {"messages": [["public question", "public answer"]]}
    with Session(engine) as session:
        session.add_all([owner, viewer, private, public])
        session.commit()
        for row in (owner, viewer, private, public):
            session.refresh(row)
    monkeypatch.setattr(module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(module.flowsettings, "KH_USER_CAN_SEE_PUBLIC", None)
    control: Any = object.__new__(module.ConversationControl)
    control._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    try:
        yield control, owner, viewer, private, public
    finally:
        with Session(engine) as session:
            for row in (private, public, owner, viewer):
                current = session.get(type(row), cast(Any, row).id)
                if current is not None:
                    session.delete(current)
            session.commit()


@pytest.mark.parametrize("allowed", [None, "control-viewer", "another-user"])
def test_history_resolves_real_identity_and_public_list_policy(
    authenticated_rows, monkeypatch, allowed
):
    control, owner, viewer, private, public = authenticated_rows
    monkeypatch.setattr(module.flowsettings, "KH_USER_CAN_SEE_PUBLIC", allowed)
    request = gr.Request(username=viewer.username)
    assert control.load_chat_history(owner.id, request) == (
        [("Public", public.id)] if allowed != "another-user" else []
    )
    monkeypatch.setattr(module.flowsettings, "KH_USER_CAN_SEE_PUBLIC", None)
    assert control.load_chat_history(
        viewer.id, gr.Request(username=owner.username)
    ) == [("Public", public.id), ("Private", private.id)]
    assert control._load_chat_history("nonexistent-user") == []


@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_public_read_does_not_grant_mutation_to_real_nonowner(
    authenticated_rows, operation
):
    from ktem.db.models import Conversation, engine
    from sqlmodel import Session

    control, owner, viewer, private, public = authenticated_rows
    request = gr.Request(username=viewer.username)
    assert control.select_conv(private.id, owner.id, request)[0] == ""
    assert control.select_conv(public.id, owner.id, request)[3] == [
        ["public question", "public answer"]
    ]
    with pytest.raises(gr.Error, match="owner scope"):
        if operation == "delete":
            control.delete_conv(public.id, owner.id, request)
        else:
            control.rename_conv(public.id, "Forged rename", True, owner.id, request)
    with Session(engine) as session:
        unchanged = session.get(Conversation, public.id)
        assert unchanged is not None and unchanged.name == "Public"


@pytest.mark.parametrize("username", [None, "removed-user"])
@pytest.mark.parametrize("method", ["new_conv", "select_conv", "delete_conv"])
def test_missing_or_expired_real_request_rejects_before_operations(
    authenticated_rows, monkeypatch, username, method
):
    control, owner, _, private, _ = authenticated_rows

    def unexpected(*args):
        pytest.fail("A service must not be constructed before identity is resolved")

    monkeypatch.setattr(control, "_get_session_service", unexpected)
    monkeypatch.setattr(control, "_get_mutation_service", unexpected)
    args = () if method == "new_conv" else (private.id,)
    with pytest.raises(gr.Error, match="Authenticated user identity is unavailable"):
        getattr(control, method)(*args, owner.id, gr.Request(username=username))
