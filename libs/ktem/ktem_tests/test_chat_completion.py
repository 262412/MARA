from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import gradio as gr
import pytest
from gradio.helpers import special_args
from ktem.pages.chat.chat_completion import CompletionTail, with_completion_context


@pytest.fixture
def completion():
    session = SimpleNamespace(
        messages=[("question", "answer")],
        retrieval_messages=["citation"],
        plot_history=[None],
        state={"app": {"regen": False}, "terminal": {"commit": "owned"}},
        graph_source_ids=["document"],
    )
    tail = CompletionTail(
        resolve_user=Mock(return_value="real-owner"),
        load_session=Mock(return_value=session),
        suggest_name=Mock(return_value=("Name", True)),
        rename_conversation=Mock(return_value=("choices", "id", "name")),
        persist_data_source=Mock(return_value=(["citation"], [None])),
    )
    context = {
        "conversation_id": "id",
        "view_revision": 0,
        "messages": [["question", "answer"]],
        "selecteds": ("select", ["document"], "real-owner"),
    }
    return tail, context, session


def test_stream_adapter_captures_scope_without_changing_old_callback():
    request = gr.Request(username="owner", session_hash="browser")
    selected = ["document"]
    history = [["question", "answer"]]
    calls = []

    def old(conversation_id, request: gr.Request, *selecteds):
        calls.append((conversation_id, request, selecteds))
        yield (*range(13), history)

    adapted = with_completion_context(old)
    inputs, _, _ = special_args(adapted, ["id", selected], request=request)
    result = list(adapted(*inputs))[0]
    assert result[:14] == (*range(13), history)
    assert calls == [("id", request, (selected,))]
    selected.append("changed")
    history[0][1] = "changed"
    assert result[14] == {
        "conversation_id": "id",
        "view_revision": 0,
        "messages": [["question", "answer"]],
        "selecteds": (["document"],),
    }
    assert adapted.__wrapped__ is old


def test_completed_tail_uses_real_request_and_finalizer_payload(completion):
    tail, context, session = completion
    request = gr.Request(username="owner")
    messages = context["messages"]
    before = deepcopy(vars(session))
    assert tail.suggest("id", "forged", messages, context, request) == ("Name", True)
    assert tail.rename("id", "Name", True, "forged", messages, context, request) == (
        "choices",
        "id",
        "name",
    )
    assert tail.persist(
        "id",
        "forged",
        "mindmap-not-citations",
        "stale-plot",
        ["stale"],
        [],
        messages,
        {},
        [],
        context,
        request,
        "all",
        [],
        "changed-owner",
    ) == (["citation"], [None])
    tail.load_session.assert_called_with("id", user_id="real-owner")
    tail.rename_conversation.assert_called_once_with(
        "id", "Name", True, "forged", request
    )
    tail.persist_data_source.assert_called_once_with(
        "id",
        "forged",
        "citation",
        None,
        [],
        [],
        session.messages,
        session.state,
        ["document"],
        request,
        "select",
        ["document"],
        "real-owner",
    )
    assert vars(session) == before


@pytest.mark.parametrize(
    "failure", ["absent", "view", "newer", "empty", "missing", "error"]
)
def test_incomplete_or_other_turn_never_renames_or_persists(completion, failure):
    tail, context, _ = completion
    messages = context["messages"]
    if failure == "absent":
        context = None
    elif failure == "view":
        context["conversation_id"] = "other"
    elif failure == "newer":
        messages = [["another question", "answer"]]
    elif failure == "empty":
        messages = []
    elif failure == "missing":
        tail.load_session.return_value = None
    else:
        tail.load_session.return_value.messages = []
    request = gr.Request(username="owner")
    assert tail.suggest("id", "owner", messages, context, request) == (gr.skip(), False)
    assert (
        tail.rename("id", "Name", True, "owner", messages, context, request)
        == (gr.skip(),) * 3
    )
    assert (
        tail.persist(
            "id", "owner", "", None, [], [], messages, {}, [], context, request
        )
        == (gr.skip(),) * 2
    )
    tail.suggest_name.assert_not_called()
    tail.rename_conversation.assert_not_called()
    tail.persist_data_source.assert_not_called()


def test_identity_failure_and_persistence_error_propagate_once(completion):
    tail, context, _ = completion
    error = ValueError("identity missing")
    tail.resolve_user.side_effect = error
    with pytest.raises(ValueError) as captured:
        tail.suggest("id", "owner", context["messages"], context, None)
    assert captured.value is error
    tail.load_session.assert_not_called()
    tail.resolve_user.side_effect = None
    tail.persist_data_source.side_effect = error
    with pytest.raises(ValueError) as captured:
        tail.persist(
            "id", "owner", "", None, [], [], context["messages"], {}, [], context, None
        )
    assert captured.value is error
    assert tail.persist_data_source.call_count == 1


def test_demo_name_behavior_does_not_require_a_persisted_session(completion):
    tail, _, _ = completion
    tail.demo_mode = True
    assert tail.suggest(None, None, [], None, None) == ("Name", True)
    assert tail.rename(None, "Name", True, None, [], None, None) == (
        "choices",
        "id",
        "name",
    )
    tail.load_session.assert_not_called()


def test_gradio_injects_request_into_every_tail_callback(completion):
    tail, context, _ = completion
    request = gr.Request(username="owner")
    for callback, inputs, position in (
        (tail.suggest, ["id", "owner", context["messages"], context], 4),
        (tail.rename, ["id", "Name", True, "owner", context["messages"], context], 6),
        (
            tail.persist,
            [
                "id",
                "owner",
                "",
                None,
                [],
                [],
                context["messages"],
                {},
                [],
                context,
                "select",
                [],
            ],
            10,
        ),
    ):
        actual, _, _ = special_args(callback, list(inputs), request=request)
        assert actual[position] is request
        assert actual[:position] + actual[position + 1 :] == inputs
