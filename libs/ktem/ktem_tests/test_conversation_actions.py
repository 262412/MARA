"""Use conversation result adapters with records, without constructing a page."""

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.pages.chat import conversation_actions as actions


def test_adapter_has_no_page_runtime_or_service_dependency():
    tree = ast.parse(Path(actions.__file__).read_text(encoding="utf-8"))
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


def test_plain_authorized_record_keeps_raw_messages_and_history_references():
    messages = [["question", "answer"]]
    references = ["first", "latest"]
    plots = [None, {"plot": [1]}]
    state = {"nested": {"answer": 7}}
    selected = {"5": ["document"]}
    defaults = [["default"]]
    record = SimpleNamespace(
        conversation_id="id",
        name="Name",
        is_public=True,
        user_id="owner",
        data_source={"messages": messages},
        messages=[("different", "projection")],
        selected_mapping=selected,
        retrieval_messages=references,
        plot_history=plots,
        state=state,
    )
    outputs, mapping = actions.selected_conversation_outputs(record, "owner", defaults)
    assert outputs == (
        "id",
        "id",
        "Name",
        messages,
        defaults,
        "latest",
        plots[-1],
        references,
        plots,
        True,
        state,
    )
    assert outputs[3] is messages and outputs[4] is defaults
    assert outputs[6] is plots[-1] and outputs[7] is references
    assert outputs[8] is plots and outputs[10] is state
    assert mapping is selected
    assert actions.selected_conversation_outputs(record, "viewer", defaults)[1] == {}


def test_empty_outputs_retain_default_state_but_allocate_empty_histories():
    suggestions = [["default"]]
    state: dict[str, Any] = {"nested": {}}
    first = actions.empty_conversation_outputs(suggestions, state)
    second = actions.empty_conversation_outputs(suggestions, state)
    assert first == ("", "", "", [], suggestions, "", None, [], [], False, state)
    assert first[4] is suggestions and first[10] is state
    for position in (3, 7, 8):
        assert first[position] is not second[position]


def test_selector_arity_zero_and_references_use_existing_index_descriptors():
    defaults = ["all", [], ""]
    indices = [
        SimpleNamespace(selector=None),
        SimpleNamespace(id=5, selector=0, default_selector=["single"]),
        SimpleNamespace(id=7, selector=(1, 2, 3), default_selector=defaults),
        SimpleNamespace(selector="ignored"),
    ]
    selected: dict[str, list[Any]] = {
        "5": ["selected"],
        "7": ["select", ["file"], "owner"],
    }
    actual = actions.selector_outputs(indices, selected)
    assert actual == [["selected"], "select", ["file"], "owner"]
    assert actual[0] is selected["5"] and actual[2] is selected["7"][1]
    default_outputs = actions.selector_outputs(indices)
    assert default_outputs == [["single"], "all", [], ""]
    assert default_outputs[2] is defaults[1]
    # An explicit invalid mapping is not the clear operation's omitted mapping.
    with pytest.raises(AttributeError):
        actions.selector_outputs(indices, None)


def test_projection_errors_are_propagated_to_the_original_control_boundary():
    with pytest.raises(AttributeError):
        actions.selected_conversation_outputs(None, "owner", [])
