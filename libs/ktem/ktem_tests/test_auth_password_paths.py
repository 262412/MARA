import hashlib
import importlib
from pathlib import Path

import gradiologin
import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from ktem.db.models import User
from ktem.pages import login as login_module


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
    assert upgraded_user.password.startswith("$2b$12$")


def test_login_accepts_bcrypt_password(monkeypatch, user_engine):
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


def test_ktem_declares_bcrypt_as_a_direct_runtime_dependency():
    pyproject = (REPO_ROOT / "libs/ktem/pyproject.toml").read_text(encoding="utf-8")

    assert '"bcrypt' in pyproject
