from __future__ import annotations

from types import SimpleNamespace

import gradio as gr
import pytest
from ktem.auth import authorization
from ktem.db.models import Settings, User, engine
from ktem.pages.resources.user import UserManagement
from ktem.pages.settings import SettingsPage
from sqlmodel import Session, select


@pytest.fixture()
def callback_users():
    admin = User(
        username="CallbackAdmin",
        username_lower="callbackadmin",
        password="hash-admin",
        admin=True,
    )
    member = User(
        username="CallbackMember",
        username_lower="callbackmember",
        password="hash-member",
        admin=False,
    )
    with Session(engine) as session:
        session.add(admin)
        session.add(member)
        session.commit()
        session.refresh(admin)
        session.refresh(member)
        ids = admin.id, member.id
    yield ids
    with Session(engine) as session:
        for user_id in ids:
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user is not None:
                session.delete(user)
        session.commit()


def test_managed_callback_uses_request_principal_not_state(
    monkeypatch,
    callback_users,
):
    admin_id, member_id = callback_users
    request = SimpleNamespace(username="CallbackMember")
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            member_id if received is request and auth_mode == "password" else None
        ),
    )

    assert authorization.resolve_callback_user_id(admin_id, request) == member_id
    with pytest.raises(authorization.CallbackAuthorizationError):
        authorization.require_admin(admin_id, request)


def test_managed_callback_without_request_identity_fails_closed(monkeypatch):
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "sso")

    with pytest.raises(authorization.CallbackAuthorizationError) as caught:
        authorization.resolve_callback_user_id("forged")
    assert isinstance(caught.value, gr.Error)
    assert str(caught.value) == "This operation is unavailable."


def test_local_callback_retains_state_user_and_rechecks_admin(
    monkeypatch,
    callback_users,
):
    admin_id, member_id = callback_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")

    assert authorization.resolve_callback_user_id(admin_id) == admin_id
    assert authorization.require_admin(admin_id) == admin_id
    with pytest.raises(authorization.CallbackAuthorizationError):
        authorization.require_admin(member_id)


def test_non_admin_user_management_denial_precedes_create_validation(
    monkeypatch,
    callback_users,
):
    _admin_id, member_id = callback_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")
    page = object.__new__(UserManagement)
    page._app = SimpleNamespace(user_id=member_id)

    with pytest.raises(authorization.CallbackAuthorizationError):
        page.create_user("x", "weak", "different")

    with Session(engine) as session:
        assert (
            session.exec(select(User).where(User.username_lower == "x")).first() is None
        )


def test_managed_settings_save_uses_request_principal(
    monkeypatch,
    callback_users,
):
    admin_id, member_id = callback_users
    request = SimpleNamespace(username="CallbackMember")
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            member_id if received is request and auth_mode == "password" else None
        ),
    )
    page = object.__new__(SettingsPage)
    page._settings_keys = ["reasoning.use"]

    assert page.save_setting(admin_id, request, "request-owned") == {
        "reasoning.use": "request-owned"
    }

    with Session(engine) as session:
        member_setting = session.exec(
            select(Settings).where(Settings.user == member_id)
        ).first()
        forged_setting = session.exec(
            select(Settings).where(Settings.user == admin_id)
        ).first()
        assert member_setting is not None
        assert member_setting.setting == {"reasoning.use": "request-owned"}
        assert forged_setting is None
        session.delete(member_setting)
        session.commit()


def test_managed_user_create_rejects_forged_admin_state(
    monkeypatch,
    callback_users,
):
    admin_id, member_id = callback_users
    request = SimpleNamespace(username="CallbackMember")
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            member_id if received is request and auth_mode == "password" else None
        ),
    )
    page = object.__new__(UserManagement)
    page._app = SimpleNamespace(user_id=admin_id)

    with pytest.raises(authorization.CallbackAuthorizationError):
        page.create_user("ForgedCreate", "StrongPass!23", "StrongPass!23", request)

    with Session(engine) as session:
        assert (
            session.exec(
                select(User).where(User.username_lower == "forgedcreate")
            ).first()
            is None
        )
