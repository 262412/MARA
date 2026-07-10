import hashlib
import importlib
import importlib.util
from types import SimpleNamespace
from typing import Any

import gradio as gr
import gradiologin
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ktem.auth.passwords import hash_password, verify_password
from ktem.auth.policy import AuthConfigurationError
from ktem.db.models import User
from ktem.pages.resources import user as user_module
from sqlmodel import Session, SQLModel, create_engine, select


def _service_module():
    module_spec = importlib.util.find_spec("ktem.auth.service")
    assert module_spec is not None, "ktem.auth.service must own server auth"
    return importlib.import_module("ktem.auth.service")


@pytest.fixture
def user_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth-service.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def _add_user(
    engine,
    *,
    username="Operator",
    password_hash=None,
    admin=True,
    user_id=None,
):
    with Session(engine) as session:
        user = User(
            id=user_id,
            username=username,
            username_lower=username.casefold(),
            password=password_hash or hash_password("CorrectHorse7!"),
            admin=admin,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return str(user.id)


def test_password_auth_callback_upgrades_legacy_hash(monkeypatch, user_engine):
    service = _service_module()
    password = "CorrectHorse7!"
    user_id = _add_user(
        user_engine,
        username="LegacyUser",
        password_hash=hashlib.sha256(password.encode()).hexdigest(),
    )
    monkeypatch.setattr(service, "engine", user_engine)

    assert service.authenticate_password(" legacyUSER ", password) is True

    with Session(user_engine) as session:
        user = session.exec(select(User).where(User.id == user_id)).one()
    assert user.password.startswith("$mara-bcrypt-sha256$$2b$12$")


def test_password_auth_callback_accepts_versioned_hash(monkeypatch, user_engine):
    service = _service_module()
    _add_user(user_engine, username="BcryptUser")
    monkeypatch.setattr(service, "engine", user_engine)

    assert service.authenticate_password("BcryptUser", "CorrectHorse7!") is True


def test_password_auth_callback_equalizes_missing_user_failure(
    monkeypatch,
    user_engine,
):
    service = _service_module()
    calls = []

    def _verify_password(password, stored_hash):
        calls.append((password, stored_hash))
        return False, None

    monkeypatch.setattr(service, "engine", user_engine)
    monkeypatch.setattr(service, "verify_password", _verify_password)

    assert service.authenticate_password("missing", "WrongHorse7!") is False
    assert calls == [("WrongHorse7!", None)]


def test_password_auth_callback_rejects_stale_legacy_migration(monkeypatch):
    service = _service_module()
    password = "CorrectHorse7!"
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    reset_hash = hash_password("ResetHorse8!")
    stale_user = User(
        id="race-user",
        username="RaceUser",
        username_lower="raceuser",
        password=legacy_hash,
    )
    state: dict[str, Any] = {
        "password": legacy_hash,
        "rolled_back": False,
        "cas_parameters": [],
    }

    class _RaceResult:
        def first(self):
            state["password"] = reset_hash
            return stale_user

    class _RaceSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _RaceResult()

        def execute(self, statement):
            state["cas_parameters"] = list(statement.compile().params.values())
            return SimpleNamespace(rowcount=0)

        def commit(self):
            return None

        def rollback(self):
            state["rolled_back"] = True

    monkeypatch.setattr(service, "Session", _RaceSession)

    assert service.authenticate_password("RaceUser", password) is False
    assert state["password"] == reset_hash
    assert state["rolled_back"] is True
    assert legacy_hash in state["cas_parameters"]
    assert "race-user" in state["cas_parameters"]


def test_password_request_username_is_authoritative(monkeypatch, user_engine):
    service = _service_module()
    expected_id = _add_user(user_engine, username="ServerUser")
    _add_user(user_engine, username="BrowserUser")
    monkeypatch.setattr(service, "engine", user_engine)
    monkeypatch.setattr(
        gradiologin,
        "get_user",
        lambda _request: {"sub": "browser-sso-id", "email": "evil@example.test"},
    )

    request = gr.Request(username="ServerUser")

    assert service.resolve_request_user_id(request, auth_mode="password") == expected_id


def test_sso_identity_uses_only_validated_claim(monkeypatch, user_engine):
    service = _service_module()
    expected_id = _add_user(
        user_engine,
        username="person@example.test",
        user_id="validated-provider-subject",
        admin=False,
    )
    monkeypatch.setattr(service, "engine", user_engine)
    monkeypatch.setattr(
        gradiologin,
        "get_user",
        lambda _request: {
            "sub": "validated-provider-subject",
            "email": "person@example.test",
        },
    )

    request = gr.Request(username="browser-supplied-user")

    assert service.resolve_request_user_id(request, auth_mode="sso") == expected_id


def test_sso_identity_rejects_incomplete_claim(monkeypatch, user_engine):
    service = _service_module()
    monkeypatch.setattr(service, "engine", user_engine)
    monkeypatch.setattr(
        gradiologin,
        "get_user",
        lambda _request: {"email": "person@example.test"},
    )

    assert (
        service.resolve_request_user_id(
            gr.Request(username="browser-supplied-user"),
            auth_mode="sso",
        )
        is None
    )


def test_password_readiness_rejects_missing_admin(monkeypatch, user_engine):
    service = _service_module()
    monkeypatch.setattr(service, "engine", user_engine)

    with pytest.raises(
        AuthConfigurationError,
        match="MARA app init --auth-mode password",
    ):
        service.validate_password_admin_readiness()


@pytest.mark.parametrize(
    "password_hash",
    [
        hashlib.sha256(b"admin").hexdigest(),
        pytest.param(None, id="versioned-bcrypt"),
    ],
)
def test_password_readiness_rejects_active_admin_admin(
    monkeypatch,
    user_engine,
    password_hash,
):
    service = _service_module()
    _add_user(
        user_engine,
        username="admin",
        password_hash=password_hash or hash_password("admin"),
        admin=True,
    )
    monkeypatch.setattr(service, "engine", user_engine)

    with pytest.raises(
        AuthConfigurationError,
        match="admin/admin.*MARA app init --auth-mode password",
    ):
        service.validate_password_admin_readiness()


def test_password_readiness_accepts_safe_admin(monkeypatch, user_engine):
    service = _service_module()
    _add_user(user_engine, username="Operator", admin=True)
    monkeypatch.setattr(service, "engine", user_engine)

    service.validate_password_admin_readiness()


def test_provision_password_admin_creates_normalized_bcrypt_admin(
    monkeypatch,
    user_engine,
):
    service = _service_module()
    monkeypatch.setattr(service, "engine", user_engine)

    service.provision_password_admin(
        username="  NewOperator  ",
        password="CorrectHorse7!",
        force=False,
    )

    with Session(user_engine) as session:
        users = session.exec(select(User)).all()
    assert len(users) == 1
    user = users[0]
    assert user.username == "NewOperator"
    assert user.username_lower == "newoperator"
    assert user.admin is True
    assert verify_password("CorrectHorse7!", user.password) == (True, None)


def test_provision_password_admin_requires_force_for_existing_user(
    monkeypatch,
    user_engine,
):
    service = _service_module()
    original_hash = hash_password("OriginalHorse7!")
    user_id = _add_user(
        user_engine,
        username="ExistingOperator",
        password_hash=original_hash,
        admin=False,
    )
    monkeypatch.setattr(service, "engine", user_engine)

    with pytest.raises(AuthConfigurationError, match="--force"):
        service.provision_password_admin(
            username=" existingoperator ",
            password="ReplacementHorse8!",
            force=False,
        )

    with Session(user_engine) as session:
        user = session.exec(select(User).where(User.id == user_id)).one()
    assert user.password == original_hash
    assert user.admin is False


def test_provision_password_admin_force_resets_promotes_and_preserves_other_users(
    monkeypatch,
    user_engine,
):
    service = _service_module()
    target_hash = hash_password("OriginalHorse7!")
    target_id = _add_user(
        user_engine,
        username="ExistingOperator",
        password_hash=target_hash,
        admin=False,
    )
    other_hash = hash_password("OtherHorse9!")
    other_id = _add_user(
        user_engine,
        username="OtherOperator",
        password_hash=other_hash,
        admin=False,
    )
    monkeypatch.setattr(service, "engine", user_engine)

    service.provision_password_admin(
        username=" existingoperator ",
        password="ReplacementHorse8!",
        force=True,
    )

    with Session(user_engine) as session:
        target = session.exec(select(User).where(User.id == target_id)).one()
        other = session.exec(select(User).where(User.id == other_id)).one()
    assert target.username == "ExistingOperator"
    assert target.username_lower == "existingoperator"
    assert target.password != target_hash
    assert verify_password("ReplacementHorse8!", target.password) == (True, None)
    assert target.admin is True
    assert other.password == other_hash
    assert other.admin is False


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("   ", "CorrectHorse7!", "username must be nonempty"),
        ("Operator", "weak-secret", "uppercase"),
    ],
)
def test_provision_password_admin_validates_credentials_before_database_write(
    monkeypatch,
    user_engine,
    username,
    password,
    message,
):
    service = _service_module()
    monkeypatch.setattr(service, "engine", user_engine)

    with pytest.raises(AuthConfigurationError, match=message):
        service.provision_password_admin(
            username=username,
            password=password,
            force=False,
        )

    with Session(user_engine) as session:
        assert session.exec(select(User)).all() == []


@pytest.mark.parametrize(
    ("password", "confirmation", "expected"),
    [
        ("CorrectHorse7!", "CorrectHorse7!", ""),
        ("weak-secret", "weak-secret", "uppercase"),
        ("CorrectHorse7!", "DifferentHorse8!", "does not match"),
    ],
)
def test_shared_password_policy_matches_user_management_policy(
    password,
    confirmation,
    expected,
):
    from ktem.auth import passwords

    shared_error = passwords.validate_password(password, confirmation)
    ui_error = user_module.validate_password(password, confirmation)

    assert shared_error == ui_error
    assert expected in shared_error


def test_user_management_construction_does_not_bootstrap_credentials(monkeypatch):
    monkeypatch.setattr(
        user_module,
        "flowsettings",
        SimpleNamespace(
            KH_FEATURE_USER_MANAGEMENT_ADMIN="LegacyOperator",
            KH_FEATURE_USER_MANAGEMENT_PASSWORD="CorrectHorse7!",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        user_module.UserManagement,
        "on_building_ui",
        lambda _self: None,
    )
    monkeypatch.setattr(
        user_module,
        "create_user",
        lambda *_args, **_kwargs: pytest.fail(
            "launch-time UI construction must not create credentials"
        ),
    )

    user_module.UserManagement(SimpleNamespace())


def test_gradio_password_auth_issues_httponly_cookie_and_logout_clears_it(
    monkeypatch,
    user_engine,
):
    service = _service_module()
    _add_user(user_engine, username="Operator", admin=True)
    monkeypatch.setattr(service, "engine", user_engine)

    with gr.Blocks() as blocks:
        gr.Markdown("MARA auth route smoke")
    app = gr.mount_gradio_app(
        FastAPI(),
        blocks,
        path="/",
        auth=service.authenticate_password,
    )

    with TestClient(app) as client:
        login = client.post(
            "/login",
            data={"username": "Operator", "password": "CorrectHorse7!"},
        )
        assert login.status_code == 200
        assert login.json() == {"success": True}
        assert any(
            "access-token" in cookie and "httponly" in cookie.lower()
            for cookie in login.headers.get_list("set-cookie")
        )
        assert client.get("/user").json() == "Operator"

        logout = client.get("/logout", follow_redirects=False)
        assert logout.status_code == 302
        assert logout.headers["location"] == "/"
        assert client.get("/user").json() is None
