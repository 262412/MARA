from types import SimpleNamespace

from ktem.db.models import User
from slide_cli.docqa_runtime import _resolve_default_user_id
from sqlmodel import SQLModel, Session, create_engine


def _user_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def test_managed_docqa_without_a_user_returns_actionable_diagnostics(tmp_path):
    engine = _user_engine(tmp_path)
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT=True,
        KH_FEATURE_USER_MANAGEMENT_ADMIN="",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
    )

    user_id, issues = _resolve_default_user_id(settings, engine, User)

    assert user_id == ""
    assert len(issues) == 1
    assert "existing admin user" in issues[0]
    assert "KH_FEATURE_USER_MANAGEMENT_ADMIN" in issues[0]
    assert "KH_FEATURE_USER_MANAGEMENT_PASSWORD" in issues[0]


def test_managed_docqa_reuses_the_explicitly_configured_user(tmp_path):
    engine = _user_engine(tmp_path)
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT=True,
        KH_FEATURE_USER_MANAGEMENT_ADMIN="operator",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
    )
    with Session(engine) as session:
        user = User(
            username="Operator",
            username_lower="operator",
            password="existing-hash",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        expected_user_id = str(user.id)

    assert _resolve_default_user_id(settings, engine, User) == (expected_user_id, [])


def test_managed_docqa_reuses_a_fallback_admin(tmp_path):
    engine = _user_engine(tmp_path)
    settings = SimpleNamespace(
        KH_FEATURE_USER_MANAGEMENT=True,
        KH_FEATURE_USER_MANAGEMENT_ADMIN="",
        KH_FEATURE_USER_MANAGEMENT_PASSWORD="",
    )
    with Session(engine) as session:
        user = User(
            username="FallbackOperator",
            username_lower="fallbackoperator",
            password="existing-hash",
            admin=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        expected_user_id = str(user.id)

    assert _resolve_default_user_id(settings, engine, User) == (expected_user_id, [])
