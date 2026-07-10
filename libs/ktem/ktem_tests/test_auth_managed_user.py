import logging
import re
import uuid
from types import SimpleNamespace

import ktem.docqa.runtime as runtime_module
import pytest
from ktem.db.models import User, engine
from ktem.docqa.runtime import DocQARuntime
from sqlmodel import Session, select


def test_ensure_default_managed_user_reuses_existing_admin(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)
    username = f"docqa_runtime_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        username,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        "Admin123!",
        raising=False,
    )

    with Session(engine) as session:
        user = User(
            username=username,
            username_lower=username.lower(),
            password="existing-hash",
            admin=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        existing_id = str(user.id)

    try:
        assert runtime._ensure_default_managed_user() == existing_id
    finally:
        with Session(engine) as session:
            row = session.exec(
                select(User).where(User.username_lower == username.lower())
            ).one_or_none()
            if row is not None:
                session.delete(row)
                session.commit()


def test_ensure_default_managed_user_creates_missing_admin_from_safe_legacy_config(
    monkeypatch,
):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)
    username = f"docqa_runtime_{uuid.uuid4().hex[:8]}"
    password = "Admin123!"
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        username,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        password,
        raising=False,
    )
    captured: dict[str, User] = {}

    class _FakeResult:
        def first(self):
            return None

    class _FakeSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _FakeResult()

        def add(self, user):
            captured["user"] = user

        def commit(self):
            return None

        def refresh(self, user):
            if not getattr(user, "id", None):
                user.id = "created-user-id"

    monkeypatch.setattr(runtime_module, "Session", _FakeSession)

    with pytest.warns(DeprecationWarning, match="one minor release"):
        created_id = runtime._ensure_default_managed_user()
    created_user = captured["user"]

    assert str(created_user.id) == created_id
    assert created_user.username == username
    assert created_user.username_lower == username.lower()
    assert created_user.admin is True
    assert created_user.password.startswith("$mara-bcrypt-sha256$$2b$12$")


def test_ensure_default_managed_user_reuses_fallback_admin(monkeypatch):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        "",
        raising=False,
    )
    fallback_admin = SimpleNamespace(id="fallback-admin")

    class _FakeResult:
        def first(self):
            return fallback_admin

    class _FakeSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _FakeResult()

    monkeypatch.setattr(runtime_module, "Session", _FakeSession)

    assert runtime._ensure_default_managed_user() == "fallback-admin"


@pytest.mark.parametrize(
    ("username", "password", "diagnostic"),
    [
        ("", "", "existing admin user"),
        ("operator", "", "both.*nonempty"),
        ("admin", "admin", "admin/admin"),
    ],
)
def test_ensure_default_managed_user_does_not_create_unsafe_defaults(
    monkeypatch,
    caplog,
    username,
    password,
    diagnostic,
):
    runtime = object.__new__(DocQARuntime)
    runtime._app = SimpleNamespace(f_user_management=True)
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN",
        username,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module.flowsettings,
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD",
        password,
        raising=False,
    )

    class _FakeResult:
        def first(self):
            return None

    class _FakeSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _FakeResult()

        def add(self, _user):
            pytest.fail("unsafe/default credentials must not create a user")

    monkeypatch.setattr(runtime_module, "Session", _FakeSession)

    with caplog.at_level(logging.WARNING):
        if username or password:
            with pytest.warns(DeprecationWarning):
                user_id = runtime._ensure_default_managed_user()
        else:
            user_id = runtime._ensure_default_managed_user()

    assert user_id == ""
    assert caplog.text.lower()
    assert re.search(diagnostic, caplog.text, re.IGNORECASE)
