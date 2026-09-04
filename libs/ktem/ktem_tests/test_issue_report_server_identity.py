from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from ktem.auth.authorization import CallbackAuthorizationError
from ktem.db.models import Conversation, IssueReport, engine
from ktem.pages.chat import report as report_module
from ktem.pages.chat.report import ReportIssue
from sqlmodel import Session, select


@pytest.fixture()
def report_conversation():
    conversation = Conversation(user="report-owner", is_public=False)
    conversation.data_source = {"private_marker": "DO-NOT-READ-SERVER-HISTORY"}
    with Session(engine) as session:
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        conversation_id = conversation.id
    yield conversation_id
    with Session(engine) as session:
        reports = session.exec(select(IssueReport)).all()
        for report in reports:
            if (report.chat or {}).get("conv_id") == conversation_id:
                session.delete(report)
        row = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).first()
        if row is not None:
            session.delete(row)
        session.commit()


def _reporter() -> ReportIssue:
    reporter = object.__new__(ReportIssue)
    reporter._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
    return reporter


def test_issue_report_rejects_private_non_owner_before_write(
    monkeypatch,
    report_conversation,
):
    monkeypatch.setattr(
        report_module,
        "resolve_callback_user_id",
        lambda _state, _request: "attacker",
    )
    before = len(Session(engine).exec(select(IssueReport)).all())

    with pytest.raises(CallbackAuthorizationError):
        _reporter().report(
            "incorrect",
            ["wrong-evidence"],
            "submitted marker",
            report_conversation,
            [("submitted", "history")],
            {"submitted": "settings"},
            "forged-owner",
            "submitted info",
            {"submitted": "state"},
            SimpleNamespace(username="attacker"),
        )

    with Session(engine) as session:
        assert len(session.exec(select(IssueReport)).all()) == before


def test_issue_report_records_resolved_owner_without_loading_server_chat(
    monkeypatch,
    report_conversation,
):
    monkeypatch.setattr(
        report_module,
        "resolve_callback_user_id",
        lambda _state, _request: "report-owner",
    )

    _reporter().report(
        "correct",
        [],
        "submitted only",
        report_conversation,
        [("submitted question", "submitted answer")],
        {"submitted": "settings"},
        "forged-user",
        "submitted info",
        {"submitted": "state"},
        SimpleNamespace(username="owner"),
    )

    with Session(engine) as session:
        report = session.exec(
            select(IssueReport).where(IssueReport.user == "report-owner")
        ).first()
    assert report is not None
    assert report.chat["chat_history"] == [["submitted question", "submitted answer"]]
    assert "DO-NOT-READ-SERVER-HISTORY" not in str(report.chat)


@pytest.mark.parametrize("conversation_kind", ["owner", "public", "empty"])
def test_issue_report_allows_owner_public_and_empty_conversation_ids(
    monkeypatch,
    conversation_kind,
):
    principal = "allowed-reporter"
    conversation = None
    if conversation_kind != "empty":
        conversation = Conversation(
            user=principal if conversation_kind == "owner" else "other-owner",
            is_public=conversation_kind == "public",
        )
        with Session(engine) as session:
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            conversation_id = conversation.id
    else:
        conversation_id = ""
    monkeypatch.setattr(
        report_module,
        "resolve_callback_user_id",
        lambda _state, _request: principal,
    )

    _reporter().report(
        "correct",
        [],
        "allowed",
        conversation_id,
        [],
        {},
        "forged",
        "",
        {},
        SimpleNamespace(username="allowed"),
    )

    with Session(engine) as session:
        report = session.exec(
            select(IssueReport).where(IssueReport.user == principal)
        ).first()
        assert report is not None
        session.delete(report)
        if conversation is not None:
            stored = session.get(Conversation, conversation_id)
            assert stored is not None
            session.delete(stored)
        session.commit()


def test_issue_report_request_injection_preserves_dynamic_index_inputs(
    monkeypatch,
):
    principal = "selector-reporter"
    reporter = object.__new__(ReportIssue)
    reporter._app = SimpleNamespace(
        index_manager=SimpleNamespace(
            indices=[
                SimpleNamespace(id="single", selector=0),
                SimpleNamespace(id="pair", selector=(1, 2)),
            ]
        )
    )
    request = SimpleNamespace(username="selector")
    monkeypatch.setattr(
        report_module,
        "resolve_callback_user_id",
        lambda _state, received: principal if received is request else None,
    )

    reporter.report(
        "correct",
        [],
        "selector evidence",
        "",
        [],
        {},
        "forged",
        "",
        {},
        request,
        "first",
        "second",
        "third",
    )

    with Session(engine) as session:
        report = session.exec(
            select(IssueReport).where(IssueReport.user == principal)
        ).first()
        assert report is not None
        assert report.chat["selecteds"] == {
            "single": "first",
            "pair": ["second", "third"],
        }
        session.delete(report)
        session.commit()

    parameters = list(inspect.signature(ReportIssue.report).parameters)
    assert parameters[-2:] == ["request", "selecteds"]
    assert (
        inspect.signature(ReportIssue.report).parameters["request"].annotation
        is report_module.gr.Request
    )
