from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from ktem.auth import authorization
from ktem.auth.passwords import verify_password
from ktem.db.models import Settings, User, engine
from ktem.pages import settings as settings_module
from ktem.pages.settings import SettingsPage
from sqlmodel import Session, select


@pytest.fixture()
def settings_users():
    victim = User(
        username="SettingsVictim",
        username_lower="settingsvictim",
        password="victim-original",
    )
    principal = User(
        username="SettingsPrincipal",
        username_lower="settingsprincipal",
        password="principal-original",
    )
    with Session(engine) as session:
        session.add(victim)
        session.add(principal)
        session.commit()
        session.refresh(victim)
        session.refresh(principal)
        victim_id, principal_id = victim.id, principal.id
        session.add(Settings(user=victim_id, setting={"mode": "victim"}))
        session.add(Settings(user=principal_id, setting={"mode": "principal"}))
        session.commit()
    yield victim_id, principal_id
    with Session(engine) as session:
        for row in session.exec(select(Settings)).all():
            if row.user in {victim_id, principal_id}:
                session.delete(row)
        for user_id in (victim_id, principal_id):
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user is not None:
                session.delete(user)
        session.commit()


def _page() -> SettingsPage:
    page = object.__new__(SettingsPage)
    page._settings_dict = {"mode": "default", "new": "preserved"}
    page._settings_keys = ["mode", "new"]
    return page


def _managed_principal(monkeypatch, request, principal_id):
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(
        authorization,
        "resolve_request_user_id",
        lambda received, *, auth_mode: (
            principal_id if received is request and auth_mode == "password" else None
        ),
    )


def test_managed_settings_load_uses_request_principal_not_state_user(
    monkeypatch,
    settings_users,
):
    victim_id, principal_id = settings_users
    request = SimpleNamespace(username="SettingsPrincipal")
    _managed_principal(monkeypatch, request, principal_id)

    assert _page().load_setting(victim_id, request) == [
        {"mode": "principal", "new": "preserved"},
        "principal",
        "preserved",
    ]


def test_password_change_updates_only_request_principal(
    monkeypatch,
    settings_users,
):
    victim_id, principal_id = settings_users
    request = SimpleNamespace(username="SettingsPrincipal")
    _managed_principal(monkeypatch, request, principal_id)

    assert _page().change_password(
        victim_id,
        "StrongPass!23",
        "StrongPass!23",
        request,
    ) == ("", "")

    with Session(engine) as session:
        victim = session.get(User, victim_id)
        principal = session.get(User, principal_id)
        assert victim is not None and victim.password == "victim-original"
        assert principal is not None
        assert verify_password("StrongPass!23", principal.password)[0]


def test_missing_managed_request_performs_no_settings_or_user_write(
    monkeypatch,
    settings_users,
):
    victim_id, principal_id = settings_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "password")

    with pytest.raises(authorization.CallbackAuthorizationError):
        _page().save_setting(victim_id, "forged", "forged")
    with pytest.raises(authorization.CallbackAuthorizationError):
        _page().change_password(
            victim_id,
            "StrongPass!23",
            "StrongPass!23",
        )

    with Session(engine) as session:
        victim = session.get(User, victim_id)
        principal = session.get(User, principal_id)
        victim_settings = session.exec(
            select(Settings).where(Settings.user == victim_id)
        ).one()
        assert victim is not None and victim.password == "victim-original"
        assert principal is not None and principal.password == "principal-original"
        assert victim_settings.setting == {"mode": "victim"}


def test_local_mode_retains_state_settings_behavior(monkeypatch, settings_users):
    victim_id, _principal_id = settings_users
    monkeypatch.setattr(authorization.flowsettings, "MARA_AUTH_MODE", "local")

    assert _page().load_setting(victim_id) == [
        {"mode": "victim", "new": "preserved"},
        "victim",
        "preserved",
    ]


def test_signout_reset_reads_defaults_without_database_lookup(
    monkeypatch,
):
    def unexpected_session(*_args, **_kwargs):
        raise AssertionError("sign-out defaults must not query user settings")

    monkeypatch.setattr(settings_module, "Session", unexpected_session)
    assert _page().load_default_setting() == [
        {"mode": "default", "new": "preserved"},
        "default",
        "preserved",
    ]


def test_settings_request_is_special_without_component_abi_change():
    save_parameters = list(inspect.signature(SettingsPage.save_setting).parameters)
    change_parameters = list(inspect.signature(SettingsPage.change_password).parameters)

    assert save_parameters == ["self", "user_id", "request", "args"]
    assert change_parameters == [
        "self",
        "user_id",
        "password",
        "password_confirm",
        "request",
    ]
    assert (
        inspect.signature(SettingsPage.save_setting).parameters["request"].annotation
        is settings_module.gr.Request
    )
