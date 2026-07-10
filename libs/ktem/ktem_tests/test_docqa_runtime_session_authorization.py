from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from ktem.db.models import Conversation, engine
from ktem.docqa.runtime import DocQARuntime
from sqlmodel import Session, select


def _runtime(user_id: str) -> DocQARuntime:
    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._user_id = user_id
    runtime._app = SimpleNamespace(
        default_settings=SimpleNamespace(flatten=lambda: {}),
        index_manager=SimpleNamespace(indices=[]),
    )
    runtime.file_index = None
    return runtime


def _conversation(
    *,
    user: str,
    name: str,
    is_public: bool = False,
    data_source: dict[str, Any] | None = None,
) -> Conversation:
    row = Conversation(user=user, name=name, is_public=is_public)
    row.data_source = data_source or {"origin": "cli"}
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _delete_conversations(*conversation_ids: str) -> None:
    with Session(engine) as session:
        for conversation_id in conversation_ids:
            row = session.exec(
                select(Conversation).where(Conversation.id == conversation_id)
            ).one_or_none()
            if row is not None:
                session.delete(row)
        session.commit()


def test_runtime_session_reads_are_scoped_to_owner_or_public():
    owner_id = "session-owner"
    viewer_id = "session-viewer"
    owned = _conversation(user=viewer_id, name="Owned")
    public = _conversation(user=owner_id, name="Public", is_public=True)
    private = _conversation(user=owner_id, name="Private")
    runtime = _runtime(viewer_id)

    try:
        summaries = runtime.list_sessions()
        visible_ids = {summary.conversation_id for summary in summaries}

        assert owned.id in visible_ids
        assert public.id in visible_ids
        assert private.id not in visible_ids
        assert runtime.load_session(owned.id) is not None
        assert runtime.load_session(public.id) is not None
        assert runtime.load_session(private.id) is None
    finally:
        _delete_conversations(owned.id, public.id, private.id)


def test_runtime_session_load_preserves_legacy_graph_fallback_and_shape():
    row = _conversation(
        user="shape-owner",
        name="Legacy",
        data_source={
            "origin": "web",
            "messages": [["question", "answer"]],
            "retrieval_messages": ["refs"],
            "plot_history": [{"plot": 1}],
            "state": {"app": {"regen": False}},
            "selected": {"9": ["select", ["file-2", "file-1"], "shape-owner"]},
        },
    )
    runtime = _runtime("shape-owner")

    try:
        loaded = runtime.load_session(row.id)

        assert loaded is not None
        assert loaded.conversation_id == row.id
        assert loaded.name == "Legacy"
        assert loaded.user_id == "shape-owner"
        assert loaded.messages == [("question", "answer")]
        assert loaded.retrieval_messages == ["refs"]
        assert loaded.plot_history == [{"plot": 1}]
        assert loaded.state == {"app": {"regen": False}}
        assert loaded.selected_mapping == {
            "9": ["select", ["file-2", "file-1"], "shape-owner"]
        }
        assert loaded.graph_source_ids == ["file-2", "file-1"]
        assert loaded.origin == "web"
    finally:
        _delete_conversations(row.id)


def test_runtime_rejects_private_non_owner_persistence():
    row = _conversation(
        user="private-owner",
        name="Private",
        data_source={
            "origin": "cli",
            "selected": {"9": ["select", ["original"], "private-owner"]},
            "messages": [],
        },
    )
    runtime = _runtime("other-user")

    try:
        with pytest.raises(PermissionError, match="authenticated user scope"):
            runtime.persist_conversation_state(
                conversation_id=row.id,
                user_id="other-user",
                retrieval_message="refs",
                plot_data=None,
                retrieval_history=[],
                plot_history=[],
                messages=[("question", "unauthorized answer")],
                state={"app": {"regen": False}},
                graph_source_ids=["stolen"],
                selected_file_ids=["stolen"],
                origin="web",
            )

        with Session(engine) as session:
            unchanged = session.exec(
                select(Conversation).where(Conversation.id == row.id)
            ).one()
        assert unchanged.data_source["messages"] == []
        assert unchanged.data_source["selected"] == {
            "9": ["select", ["original"], "private-owner"]
        }
    finally:
        _delete_conversations(row.id)


def test_public_non_owner_persistence_keeps_owner_selection_mapping():
    row = _conversation(
        user="public-owner",
        name="Public",
        is_public=True,
        data_source={
            "origin": "cli",
            "selected": {"9": ["select", ["owner-file"], "public-owner"]},
            "messages": [],
        },
    )
    runtime = _runtime("public-viewer")

    try:
        runtime.persist_conversation_state(
            conversation_id=row.id,
            user_id="public-viewer",
            retrieval_message="refs",
            plot_data=None,
            retrieval_history=[],
            plot_history=[],
            messages=[("question", "public answer")],
            state={"app": {"regen": False}},
            graph_source_ids=["viewer-file"],
            selected_file_ids=["viewer-file"],
            origin="web",
        )

        with Session(engine) as session:
            updated = session.exec(
                select(Conversation).where(Conversation.id == row.id)
            ).one()
        assert updated.data_source["messages"] == [["question", "public answer"]]
        assert updated.data_source["selected"] == {
            "9": ["select", ["owner-file"], "public-owner"]
        }
    finally:
        _delete_conversations(row.id)


@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("delete_session", ()),
        ("rename_session", ("Stolen name",)),
        ("update_chat_suggestions", (["stolen suggestion"],)),
    ],
)
def test_runtime_session_mutations_require_owner(operation, arguments):
    row = _conversation(
        user="mutation-owner",
        name="Protected",
        is_public=True,
        data_source={"origin": "web", "messages": []},
    )
    runtime = _runtime("other-user")

    try:
        with pytest.raises(PermissionError, match="owner scope"):
            getattr(runtime, operation)(row.id, *arguments, user_id="other-user")

        with Session(engine) as session:
            unchanged = session.exec(
                select(Conversation).where(Conversation.id == row.id)
            ).one()
        assert unchanged.name == "Protected"
        assert "chat_suggestions" not in unchanged.data_source
    finally:
        _delete_conversations(row.id)


def test_runtime_owner_can_rename_update_and_delete_session():
    row = _conversation(
        user="mutation-owner",
        name="Original",
        data_source={"origin": "web", "messages": []},
    )
    runtime = _runtime("mutation-owner")

    runtime.rename_session(row.id, "Renamed")
    runtime.update_chat_suggestions(row.id, ["Next question"])
    with Session(engine) as session:
        updated = session.exec(
            select(Conversation).where(Conversation.id == row.id)
        ).one()
    assert updated.name == "Renamed"
    assert updated.data_source["chat_suggestions"] == [["Next question"]]

    runtime.delete_session(row.id)
    with Session(engine) as session:
        assert (
            session.exec(
                select(Conversation).where(Conversation.id == row.id)
            ).one_or_none()
            is None
        )
