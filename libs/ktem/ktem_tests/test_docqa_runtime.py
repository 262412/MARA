import hashlib
import uuid
from types import SimpleNamespace

from sqlmodel import Session, select

import ktem.docqa.runtime as runtime_module
from ktem.db.models import User, engine
from ktem.docqa.runtime import DocQARuntime


def test_extract_selected_ids_from_data_source_handles_cli_shape():
    data_source = {
        "selected": {
            "1": ["select", ["file-1", "file-2"], "default"],
            "2": ["all", [], "default"],
        }
    }

    assert DocQARuntime._extract_selected_ids_from_data_source(data_source) == [
        "file-1",
        "file-2",
    ]


def test_merge_unique_file_ids_preserves_order():
    assert DocQARuntime._merge_unique_file_ids(
        ["file-1", "file-2"],
        ["file-2", "file-3"],
        "file-4",
    ) == ["file-1", "file-2", "file-3", "file-4"]


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


def test_ensure_default_managed_user_creates_missing_admin(monkeypatch):
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

    created_id = runtime._ensure_default_managed_user()
    created_user = captured["user"]

    assert str(created_user.id) == created_id
    assert created_user.username == username
    assert created_user.username_lower == username.lower()
    assert created_user.admin is True
    assert created_user.password == hashlib.sha256(password.encode()).hexdigest()
