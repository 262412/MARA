from __future__ import annotations

from types import SimpleNamespace

import pytest
from ktem.auth import authorization
from ktem.db.models import User, engine
from ktem.pages.resources import ResourcesTab
from ktem.pages.resources import user as user_module
from ktem.pages.resources.user import UserManagement
from sqlmodel import Session, select


@pytest.fixture()
def managed_users():
    admin = User(
        username="ManagedAdmin",
        username_lower="managedadmin",
        password="admin-original",
        admin=True,
    )
    member = User(
        username="ManagedMember",
        username_lower="managedmember",
        password="member-original",
        admin=False,
    )
    target = User(
        username="ManagedTarget",
        username_lower="managedtarget",
        password="target-original",
        admin=False,
    )
    with Session(engine) as session:
        session.add(admin)
        session.add(member)
        session.add(target)
        session.commit()
        session.refresh(admin)
        session.refresh(member)
        session.refresh(target)
        ids = admin.id, member.id, target.id
    yield ids
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            if user.id in ids or user.username_lower == "managedcreated":
                session.delete(user)
        session.commit()


def _page(state_user_id) -> UserManagement:
    page = object.__new__(UserManagement)
    page._app = SimpleNamespace(user_id=state_user_id)
    return page


def _deny_before_page_session(monkeypatch, callback):
    def unexpected_session(*_args, **_kwargs):
        raise AssertionError("target database access occurred after admin denial")

    monkeypatch.setattr(user_module, "Session", unexpected_session)
    with pytest.raises(authorization.CallbackAuthorizationError):
        callback()


def test_non_admin_cannot_reach_user_database_callbacks(
    monkeypatch,
    managed_users,
):
    _admin_id, member_id, target_id = managed_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")
    page = _page(member_id)

    callbacks = [
        lambda: page.create_user("x", "weak", "different"),
        lambda: page.list_users(member_id),
        lambda: page.on_selected_user_change(target_id),
        lambda: page.save_user(target_id, "changed", "", "", True),
        lambda: page.delete_user(member_id, target_id),
    ]
    for callback in callbacks:
        _deny_before_page_session(monkeypatch, callback)


def test_forged_admin_state_loses_to_non_admin_request(
    monkeypatch,
    managed_users,
):
    admin_id, member_id, _target_id = managed_users
    request = SimpleNamespace(username="ManagedMember")
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            member_id if received is request and auth_mode == "password" else None
        ),
    )

    with pytest.raises(authorization.CallbackAuthorizationError):
        _page(admin_id).create_user(
            "ManagedCreated",
            "StrongPass!23",
            "StrongPass!23",
            request,
        )


def test_admin_can_create_list_read_save_and_delete_other_user(
    monkeypatch,
    managed_users,
):
    admin_id, _member_id, target_id = managed_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")
    page = _page(admin_id)

    assert page.create_user(
        "ManagedCreated",
        "StrongPass!23",
        "StrongPass!23",
    ) == ("", "", "")
    records, frame = page.list_users(admin_id)
    assert list(frame.columns) == ["id", "username", "admin"]
    assert any(record["id"] == target_id for record in records)
    detail = page.on_selected_user_change(target_id)
    assert len(detail) == 9
    assert detail[5]["value"] == "ManagedTarget"
    assert page.save_user(target_id, "ManagedChanged", "", "", True) == ("", "")
    assert page.delete_user(admin_id, target_id) == -1

    with Session(engine) as session:
        assert session.get(User, target_id) is None
        changed = session.exec(
            select(User).where(User.username_lower == "managedchanged")
        ).first()
        assert changed is None


def test_admin_self_delete_uses_request_principal_and_is_denied(
    monkeypatch,
    managed_users,
):
    admin_id, member_id, _target_id = managed_users
    request = SimpleNamespace(username="ManagedAdmin")
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            admin_id if received is request and auth_mode == "password" else None
        ),
    )

    assert _page(member_id).delete_user(member_id, admin_id, request) == admin_id
    with Session(engine) as session:
        assert session.get(User, admin_id) is not None


def test_unknown_user_target_raises_neutral_authorization_error(
    monkeypatch,
    managed_users,
):
    admin_id, _member_id, _target_id = managed_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")

    with pytest.raises(
        authorization.CallbackAuthorizationError,
        match="This operation is unavailable",
    ):
        _page(admin_id).on_selected_user_change("unknown-target")


def test_resources_visibility_and_direct_call_both_require_admin(
    monkeypatch,
    managed_users,
):
    _admin_id, member_id, _target_id = managed_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")
    tab = object.__new__(ResourcesTab)

    assert tab.toggle_user_management(member_id)["visible"] is False
    with pytest.raises(authorization.CallbackAuthorizationError):
        _page(member_id).list_users(member_id)
