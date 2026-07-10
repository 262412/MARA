import sqlite3

import pytest

from ktem.auth import admin_provisioning
from ktem.auth.policy import AuthConfigurationError


def _seed_user(database_path, *, username="Existing"):
    with sqlite3.connect(database_path) as connection:
        connection.execute(admin_provisioning._USER_TABLE_DDL)
        connection.execute(
            'INSERT INTO "user" '
            "(id, username, username_lower, password, admin) VALUES (?, ?, ?, ?, ?)",
            ("existing-id", username, username.lower(), "legacy-hash", 0),
        )


def test_admin_provisioning_helpers_handle_absent_state_and_failed_rollback():
    connection = sqlite3.connect(":memory:")
    try:
        assert admin_provisioning._existing_user(connection, "missing") is None
    finally:
        connection.close()

    admin_provisioning._rollback(None)

    class _RollbackFailure:
        def rollback(self):
            raise sqlite3.OperationalError("rollback failed")

    admin_provisioning._rollback(_RollbackFailure())


def test_preflight_sanitizes_invalid_sqlite_database(tmp_path):
    database_path = tmp_path / "sql.db"
    database_path.write_bytes(b"not a sqlite database")

    with pytest.raises(AuthConfigurationError) as exc_info:
        admin_provisioning.preflight_password_admin(
            database_path=database_path,
            username="admin",
            password="CorrectHorse7!",
        )

    assert str(exc_info.value) == admin_provisioning.PASSWORD_ADMIN_DATABASE_ERROR


def test_provision_existing_user_rolls_back_without_force(tmp_path):
    database_path = tmp_path / "sql.db"
    _seed_user(database_path)

    with pytest.raises(AuthConfigurationError, match="already exists"):
        admin_provisioning.provision_password_admin(
            database_path=database_path,
            username=" existing ",
            password="CorrectHorse7!",
        )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            'SELECT password, admin FROM "user" WHERE id = "existing-id"'
        ).fetchone()
    assert row == ("legacy-hash", 0)


def test_provision_sanitizes_database_path_error(tmp_path):
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")

    with pytest.raises(AuthConfigurationError) as exc_info:
        admin_provisioning.provision_password_admin(
            database_path=parent_file / "sql.db",
            username="admin",
            password="CorrectHorse7!",
        )

    assert str(exc_info.value) == admin_provisioning.PASSWORD_ADMIN_DATABASE_ERROR


def test_provision_rolls_back_and_reraises_unexpected_hash_failure(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "sql.db"

    def fail_hash(_password):
        raise RuntimeError("hash backend failed")

    monkeypatch.setattr(admin_provisioning, "hash_password", fail_hash)

    with pytest.raises(RuntimeError, match="hash backend failed"):
        admin_provisioning.provision_password_admin(
            database_path=database_path,
            username="admin",
            password="CorrectHorse7!",
        )

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'user'"
        ).fetchone()
    assert table is None
