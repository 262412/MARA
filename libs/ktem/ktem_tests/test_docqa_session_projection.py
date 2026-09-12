"""Fixed record-conversion expectations, first run on the original service."""

from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import _runtime_selection, _runtime_sessions
from ktem.docqa._runtime_models import DocQASession, DocQASessionSummary
from ktem.docqa._runtime_session_service import RuntimeSessionService

CREATED = datetime(2026, 9, 1, 10, 20, tzinfo=timezone.utc)
UPDATED = datetime(2026, 9, 2, 11, 30)


def _row(data_source=None, **overrides):
    values = dict(
        id="conversation-1",
        name="Recorded session",
        user="owner-1",
        is_public=False,
        data_source=data_source,
        date_created=CREATED,
        date_updated=UPDATED,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def projection():
    return SimpleNamespace(
        summary=RuntimeSessionService._session_summary,
        loaded=RuntimeSessionService._loaded_session,
    )


@pytest.mark.parametrize(
    "data_source",
    [
        None,
        {},
        {
            "messages": None,
            "retrieval_messages": None,
            "plot_history": None,
            "selected": None,
            "state": None,
            "graph_source_ids": None,
            "origin": None,
        },
    ],
)
def test_empty_record_has_original_defaults(projection, data_source):
    row = _row(data_source)
    summary = projection.summary(row)
    assert type(summary) is DocQASessionSummary
    assert vars(summary) == {
        "conversation_id": "conversation-1",
        "name": "Recorded session",
        "message_count": 0,
        "graph_source_count": 0,
        "origin": "",
        "is_public": False,
        "date_created": CREATED,
        "date_updated": UPDATED,
    }
    loaded = projection.loaded(row)
    assert type(loaded) is DocQASession
    assert vars(loaded) == {
        "conversation_id": "conversation-1",
        "name": "Recorded session",
        "user_id": "owner-1",
        "is_public": False,
        "data_source": data_source or {},
        "messages": [],
        "retrieval_messages": [],
        "plot_history": [],
        "state": {"app": {"regen": False}},
        "selected_mapping": {},
        "graph_source_ids": [],
        "origin": "",
        "date_created": CREATED,
        "date_updated": UPDATED,
    }
    assert loaded.state is not _runtime_sessions.STATE
    assert loaded.state["app"] is not _runtime_sessions.STATE["app"]


def test_complete_record_preserves_original_values_and_dto_identity(projection):
    source: dict[str, Any] = {
        "messages": [["question-1", "answer-1"], ["question-2", "answer-2"]],
        "retrieval_messages": ["refs-1", "refs-2"],
        "plot_history": [{"data": [1, 2]}],
        "state": {"app": {"regen": True}, "custom": {"values": [3]}},
        "selected": {"9": ["select", ["selected-only"], "owner-1"]},
        "graph_source_ids": ["graph-2", "graph-1"],
        "origin": "web",
    }
    row = _row(source, is_public=True)
    loaded = projection.loaded(row)
    assert vars(loaded) == {
        "conversation_id": "conversation-1",
        "name": "Recorded session",
        "user_id": "owner-1",
        "is_public": True,
        "data_source": source,
        "messages": [("question-1", "answer-1"), ("question-2", "answer-2")],
        "retrieval_messages": ["refs-1", "refs-2"],
        "plot_history": [{"data": [1, 2]}],
        "state": {"app": {"regen": True}, "custom": {"values": [3]}},
        "selected_mapping": {"9": ["select", ["selected-only"], "owner-1"]},
        "graph_source_ids": ["graph-2", "graph-1"],
        "origin": "web",
        "date_created": CREATED,
        "date_updated": UPDATED,
    }
    summary = projection.summary(row)
    assert summary.as_dict() == {
        "conversation_id": "conversation-1",
        "name": "Recorded session",
        "message_count": 2,
        "graph_source_count": 2,
        "origin": "web",
        "is_public": True,
        "date_created": "2026-09-01T10:20:00+00:00",
        "date_updated": "2026-09-02T11:30:00",
    }
    for result in (loaded, summary):
        assert result.date_created is CREATED
        assert result.date_updated is UPDATED
        assert type(result).__module__ == "ktem.docqa._runtime_models"


@pytest.mark.parametrize(
    "history, expected",
    [
        (None, ["", ""]),
        ([], ["", ""]),
        (["a"], ["a", ""]),
        (["a", "b"], ["a", "b"]),
        (["a", "b", "extra"], ["a", "b"]),
    ],
)
def test_retrieval_history_alignment(projection, history, expected):
    source = {"messages": [["q1", "a1"], ["q2", "a2"]], "retrieval_messages": history}
    loaded = projection.loaded(_row(source))
    assert loaded.messages == [("q1", "a1"), ("q2", "a2")]
    assert loaded.retrieval_messages == expected
    assert loaded.retrieval_messages is not history
    assert source["retrieval_messages"] is history
    assert (
        projection.loaded(_row({"retrieval_messages": ["orphan"]})).retrieval_messages
        == []
    )


@pytest.mark.parametrize("source", [{}, {"state": None}, {"state": {}}])
def test_default_state_is_read_at_call_time_and_deep_copied(
    projection, monkeypatch, source
):
    for value in ("first", "second"):
        default: dict[str, Any] = {
            "app": {"regen": False},
            "extra": {"values": [value]},
        }
        monkeypatch.setattr(_runtime_sessions, "STATE", default)
        loaded = projection.loaded(_row(source))
        assert loaded.state == {"app": {"regen": False}, "extra": {"values": [value]}}
        loaded.state["extra"]["values"].append("copy-only")
        assert default["extra"]["values"] == [value]
        assert "state" not in source or source["state"] in (None, {})


@pytest.mark.parametrize(
    "ids, expected, count",
    [
        (
            ["same", "same", "  ", " x ", "", None, 0, False],
            ["same", "same", "  ", " x ", "0", "False"],
            6,
        ),
        (" one ", [" one "], 1),
        (0, ["0"], 1),
        (False, ["False"], 1),
        ([], ["fallback-2", "fallback-1"], 0),
        (None, ["fallback-2", "fallback-1"], 0),
        ("", ["fallback-2", "fallback-1"], 0),
    ],
)
def test_explicit_graph_ids_and_selected_fallback_are_distinct(
    projection, ids, expected, count
):
    row = _row(
        {
            "graph_source_ids": ids,
            "selected": {
                "9": [
                    "select",
                    [" fallback-2 ", "fallback-1", "fallback-2", "", None, 0, False],
                    "owner-1",
                ]
            },
        }
    )
    assert projection.summary(row).graph_source_count == count
    assert projection.loaded(row).graph_source_ids == expected
    del row.data_source["graph_source_ids"]
    assert projection.summary(row).graph_source_count == 0
    assert projection.loaded(row).graph_source_ids == ["fallback-2", "fallback-1"]


def test_copy_boundaries_match_the_original_record(projection):
    question = {"text": ["question"]}
    original_tuple = ("existing", "tuple")
    source: dict[str, Any] = {
        "messages": [[question, "answer"], original_tuple],
        "retrieval_messages": ["refs"],
        "plot_history": [{"points": [1]}],
        "state": {"app": {"regen": True}, "custom": {"values": [2]}},
        "selected": {"9": ["select", ["file-1"], "owner-1"]},
        "graph_source_ids": ["graph-1"],
        "extra": {"values": [3]},
    }
    loaded = projection.loaded(_row(source))
    assert loaded.data_source is not source
    for key in source:
        assert loaded.data_source[key] is source[key]
    assert loaded.messages is not source["messages"]
    assert loaded.messages[0] == (question, "answer")
    assert loaded.messages[0][0] is question
    assert loaded.messages[1] is original_tuple
    assert loaded.plot_history is not source["plot_history"]
    assert loaded.plot_history[0] is source["plot_history"][0]
    assert loaded.selected_mapping is not source["selected"]
    assert loaded.selected_mapping["9"] is source["selected"]["9"]
    assert loaded.state is not source["state"]
    assert loaded.state["custom"]["values"] is not source["state"]["custom"]["values"]
    loaded.data_source["new-key"] = True
    loaded.messages.append(("copy", "only"))
    loaded.retrieval_messages.append("copy-only")
    loaded.plot_history.append({"copy": True})
    loaded.selected_mapping["new-index"] = []
    loaded.graph_source_ids.append("copy-only")
    loaded.state["custom"]["values"].append(4)
    assert "new-key" not in source and "new-index" not in source["selected"]
    assert len(source["messages"]) == 2 and len(source["plot_history"]) == 1
    assert source["retrieval_messages"] == ["refs"]
    assert source["graph_source_ids"] == ["graph-1"]
    assert source["state"]["custom"]["values"] == [2]
    loaded.messages[0][0]["text"].append("shared")
    loaded.plot_history[0]["points"].append(5)
    loaded.selected_mapping["9"][1].append("file-2")
    loaded.data_source["extra"]["values"].append(6)
    assert question["text"] == ["question", "shared"]
    assert source["plot_history"][0]["points"] == [1, 5]
    assert source["selected"]["9"][1] == ["file-1", "file-2"]
    assert source["extra"]["values"] == [3, 6]


@pytest.mark.parametrize("value", [None, 0, False, "web", 12])
def test_origin_user_public_and_dates_keep_original_conversions(projection, value):
    row = _row(
        {"origin": value},
        user=value,
        is_public=value,
        date_created=date(2026, 9, 1),
        date_updated=None,
    )
    loaded = projection.loaded(row)
    assert loaded.user_id is value
    for result in (loaded, projection.summary(row)):
        assert result.origin == ("" if value in (None, 0, False) else str(value))
        assert result.is_public is bool(value)
        assert result.date_created is row.date_created
        assert type(result.date_created) is date
        assert result.date_updated is None


@pytest.mark.parametrize("operation", ["summary", "loaded"])
def test_record_and_string_conversion_errors_propagate(projection, operation):
    convert = getattr(projection, operation)
    with pytest.raises(TypeError):
        convert(_row(42))
    with pytest.raises(TypeError):
        convert(_row({"messages": 42}))
    row = _row()
    del row.id
    with pytest.raises(AttributeError, match="id"):
        convert(row)
    failure = ValueError("original string conversion error")

    class Unstringable:
        def __str__(self):
            raise failure

    for source in ({"origin": Unstringable()}, {"graph_source_ids": [Unstringable()]}):
        with pytest.raises(ValueError) as caught:
            convert(_row(source))
        assert caught.value is failure


@pytest.mark.parametrize(
    "source",
    [
        {"messages": [None]},
        {"retrieval_messages": 42},
        {"plot_history": 42},
        {"selected": 42},
    ],
)
def test_loaded_field_conversion_errors_are_not_repaired(projection, source):
    with pytest.raises(TypeError):
        projection.loaded(_row(source))


def test_state_deepcopy_error_propagates(projection):
    failure = ValueError("original state copy error")

    class Uncopyable:
        def __deepcopy__(self, memo):
            raise failure

    with pytest.raises(ValueError) as caught:
        projection.loaded(_row({"state": {"nested": Uncopyable()}}))
    assert caught.value is failure


def test_selection_module_patch_is_consumed_at_call_time(projection, monkeypatch):
    monkeypatch.setattr(
        _runtime_selection, "normalize_selected_file_ids", lambda _: ["patched"]
    )
    assert projection.summary(_row()).graph_source_count == 1
    assert projection.loaded(_row()).graph_source_ids == ["patched"]
    monkeypatch.setattr(_runtime_selection, "normalize_selected_file_ids", lambda _: [])
    monkeypatch.setattr(
        _runtime_selection,
        "extract_selected_ids_from_data_source",
        lambda _: ["fallback-patch"],
    )
    assert projection.summary(_row()).graph_source_count == 0
    assert projection.loaded(_row()).graph_source_ids == ["fallback-patch"]


@pytest.mark.parametrize(
    "name, result",
    [("_session_summary", "DocQASessionSummary"), ("_loaded_session", "DocQASession")],
)
def test_legacy_entrypoints_remain_static_methods_with_original_signatures(
    name, result
):
    descriptor = inspect.getattr_static(RuntimeSessionService, name)
    assert isinstance(descriptor, staticmethod)
    assert list(inspect.signature(descriptor.__func__).parameters) == ["row"]
    assert descriptor.__func__.__annotations__ == {
        "row": "Conversation",
        "return": result,
    }
