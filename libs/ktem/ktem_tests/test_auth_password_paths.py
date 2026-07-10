import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gradiologin
import pytest
from ktem.db.models import User
from ktem.pages import login as login_module
from sqlmodel import Session, SQLModel, create_engine, select

REPO_ROOT = Path(__file__).resolve().parents[3]
SECURITY_PASSWORD_FILES = [
    REPO_ROOT / "libs/ktem/ktem/pages/login.py",
    REPO_ROOT / "libs/ktem/ktem/pages/resources/user.py",
    REPO_ROOT / "libs/ktem/ktem/pages/settings.py",
    REPO_ROOT / "libs/ktem/ktem/docqa/runtime.py",
]


@pytest.fixture
def user_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.mark.parametrize("source_path", SECURITY_PASSWORD_FILES)
def test_security_password_paths_do_not_hash_with_sha256(source_path):
    source = source_path.read_text(encoding="utf-8")

    assert "hashlib.sha256" not in source


def test_login_upgrades_legacy_sha256_after_success(monkeypatch, user_engine):
    password = "CorrectHorse7!"
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    with Session(user_engine) as session:
        user = User(
            username="LegacyUser",
            username_lower="legacyuser",
            password=legacy_hash,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    monkeypatch.setattr(login_module, "engine", user_engine)
    monkeypatch.setattr(gradiologin, "get_user", lambda _request: None)

    page = object.__new__(login_module.LoginPage)
    result = page.login(" legacyUSER ", password, None)

    assert result == (user_id, "", "")
    with Session(user_engine) as session:
        upgraded_user = session.exec(select(User).where(User.id == user_id)).one()
    assert upgraded_user.password.startswith("$mara-bcrypt-sha256$$2b$12$")


def test_login_accepts_versioned_bcrypt_sha256_password(monkeypatch, user_engine):
    passwords = importlib.import_module("ktem.auth.passwords")
    password = "CorrectHorse7!"
    with Session(user_engine) as session:
        user = User(
            username="BcryptUser",
            username_lower="bcryptuser",
            password=passwords.hash_password(password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    monkeypatch.setattr(login_module, "engine", user_engine)
    monkeypatch.setattr(gradiologin, "get_user", lambda _request: None)

    page = object.__new__(login_module.LoginPage)

    assert page.login("BcryptUser", password, None) == (user_id, "", "")


def test_login_missing_user_runs_password_verifier_once(monkeypatch, user_engine):
    password = "CorrectHorse7!"
    verify_calls = []
    warnings: list[str] = []

    def _verify_password(candidate, stored_hash):
        verify_calls.append((candidate, stored_hash))
        return False, None

    monkeypatch.setattr(login_module, "engine", user_engine)
    monkeypatch.setattr(login_module, "verify_password", _verify_password)
    monkeypatch.setattr(gradiologin, "get_user", lambda _request: None)
    monkeypatch.setattr(login_module.gr, "Warning", warnings.append)

    page = object.__new__(login_module.LoginPage)

    assert page.login("MissingUser", password, None) == (
        None,
        "MissingUser",
        password,
    )
    assert verify_calls == [(password, None)]
    assert warnings == ["Invalid username or password"]


def test_login_rejects_stale_legacy_auth_when_concurrent_reset_wins(monkeypatch):
    password = "CorrectHorse7!"
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    reset_hash = importlib.import_module("ktem.auth.passwords").hash_password(
        "ResetHorse8!"
    )
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
    warnings: list[str] = []

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

        def add(self, user):
            state["password"] = user.password

        def commit(self):
            return None

        def rollback(self):
            state["rolled_back"] = True

    monkeypatch.setattr(login_module, "Session", _RaceSession)
    monkeypatch.setattr(gradiologin, "get_user", lambda _request: None)
    monkeypatch.setattr(login_module.gr, "Warning", warnings.append)

    page = object.__new__(login_module.LoginPage)

    assert page.login("RaceUser", password, None) == (None, "RaceUser", password)
    assert state["password"] == reset_hash
    assert state["rolled_back"] is True
    assert legacy_hash in state["cas_parameters"]
    assert "race-user" in state["cas_parameters"]
    assert warnings == ["Invalid username or password"]


def test_ktem_declares_bcrypt_as_a_direct_runtime_dependency():
    pyproject = (REPO_ROOT / "libs/ktem/pyproject.toml").read_text(encoding="utf-8")

    assert '"bcrypt' in pyproject
