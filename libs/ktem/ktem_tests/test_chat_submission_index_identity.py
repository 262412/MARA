"""Exercise submit -> source preparation -> real file-page identity resolution."""

from types import SimpleNamespace
from typing import Any, cast

import gradio as gr
import pytest
from ktem.auth import service as auth
from ktem.db.models import User
from ktem.index.file.ui import FileIndexPage
from ktem.pages import chat as chat_module
from ktem.pages.chat import ChatPage
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def submission(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'submission-identities.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for name in ("alice", "bob"):
            session.add(
                User(
                    id=name + "-id",
                    username=name,
                    username_lower=name,
                    password="unused",
                    admin=False,
                )
            )
        session.commit()
    monkeypatch.setattr(auth, "engine", engine)
    monkeypatch.setattr(chat_module.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(chat_module, "KH_DEMO_MODE", False)
    events = []

    class Indexing:
        def index_files_with_default_loaders(self, files, **kwargs):
            events.append(("file", files, kwargs))
            return [kwargs["user_id"] + "-file"]

        def index_urls_with_default_loaders(self, urls, **kwargs):
            events.append(("url", urls, kwargs))
            return [kwargs["user_id"] + "-url"]

    index = cast(Any, object.__new__(FileIndexPage))
    index._get_indexing_service = lambda: Indexing()
    page = cast(Any, object.__new__(ChatPage))
    page.first_indexing_file_fn = index.index_fn_file_with_default_loaders
    page.first_indexing_url_fn = index.index_fn_url_with_default_loaders

    def submit(kind, request, claimed="forged-id"):
        content = (
            {"text": "question", "files": ["owned.txt"]}
            if kind == "file"
            else {"text": "https://example.org/owned-document", "files": []}
        )
        return page.submit_msg(
            content, [], claimed, {}, "existing", "Existing", [], [], "", "", request
        )

    yield SimpleNamespace(page=page, events=events, submit=submit)
    engine.dispose()


@pytest.mark.parametrize("kind", ["file", "url"])
def test_authenticated_request_reaches_real_indexing_entry(submission, kind):
    request = gr.Request(username="alice", session_hash="alice-browser")
    result = submission.submit(kind, request, claimed="bob-id")
    assert len(result) == 12
    assert result[6]["value"] == ["alice-id-" + kind]
    assert len(submission.events) == 1
    assert submission.events[0][2] == {
        "reindex": True,
        "settings": {},
        "user_id": "alice-id",
    }


@pytest.mark.parametrize("kind", ["file", "url"])
@pytest.mark.parametrize(
    "incoming_request", [None, gr.Request(), gr.Request(username="deleted-user")]
)
def test_missing_or_invalid_request_stops_before_indexing(
    submission, kind, incoming_request
):
    with pytest.raises(gr.Error, match="Authenticated user identity is unavailable"):
        submission.submit(kind, incoming_request, claimed="alice-id")
    assert submission.events == []


def test_same_page_keeps_two_browser_identities_separate(submission):
    original_file = submission.page.first_indexing_file_fn
    original_url = submission.page.first_indexing_url_fn
    for kind, user in (
        ("file", "alice"),
        ("url", "bob"),
        ("url", "alice"),
        ("file", "bob"),
    ):
        submission.submit(
            kind, gr.Request(username=user, session_hash=user), claimed="another-id"
        )
    assert [event[2]["user_id"] for event in submission.events] == [
        "alice-id",
        "bob-id",
        "alice-id",
        "bob-id",
    ]
    assert submission.page.first_indexing_file_fn is original_file
    assert submission.page.first_indexing_url_fn is original_url
    assert not any("request" in name for name in vars(submission.page))


def test_authentication_and_demo_limit_precede_bound_indexing(submission, monkeypatch):
    events = submission.events
    original_identity = chat_module.resolve_request_user_id

    def identity(request, *, auth_mode):
        events.append(("auth", request))
        return original_identity(request, auth_mode=auth_mode)

    def limit(kind, request):
        events.append(("limit", request))
        raise ValueError("Owned demo limit")

    monkeypatch.setattr(chat_module, "resolve_request_user_id", identity)
    monkeypatch.setattr(chat_module, "KH_DEMO_MODE", True)
    monkeypatch.setattr(chat_module, "check_rate_limit", limit)
    request = gr.Request(username="alice")
    with pytest.raises(ValueError, match="Owned demo limit"):
        submission.submit("file", request)
    assert events == [("auth", request), ("limit", request)]


def test_bound_requests_survive_delayed_interleaving_and_legacy_none():
    from ktem.pages.chat.chat_submission import bind_chat_indexing_request

    calls = []
    requests = [gr.Request(username="alice"), gr.Request(username="bob")]

    def operation(*args, request):
        calls.append((args, request))
        return ["id"]

    alice = bind_chat_indexing_request(operation, requests[0])
    bob = bind_chat_indexing_request(operation, requests[1])
    assert bob("url", True, {}, "forged", request=None) == ["id"]
    assert alice(["file"], False, {}, "forged", request=requests[1]) == ["id"]
    assert [call[1] for call in calls] == [requests[1], requests[0]]
    assert bind_chat_indexing_request(None, requests[0]) is None


def test_indexing_type_error_is_not_retried():
    from ktem.pages.chat.chat_submission import bind_chat_indexing_request

    calls = []
    error = TypeError("Owned indexing error")

    def operation(*args, **kwargs):
        calls.append(kwargs)
        raise error

    bound = bind_chat_indexing_request(operation, None)
    with pytest.raises(TypeError) as captured:
        bound([], True, {}, "forged")
    assert captured.value is error
    assert calls == [{"request": None}]
