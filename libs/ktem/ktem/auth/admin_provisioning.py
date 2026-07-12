"""Side-effect-free password-admin provisioning for packaged app init."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from ktem.auth.passwords import hash_password, validate_password
from ktem.auth.policy import AuthConfigurationError

PASSWORD_ADMIN_DATABASE_ERROR = "Password administrator database operation failed."
_USER_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS "user" (
    id VARCHAR NOT NULL,
    username VARCHAR NOT NULL,
    username_lower VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    admin BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (username),
    UNIQUE (username_lower)
)
"""
_USER_ID_INDEX_DDL = 'CREATE INDEX IF NOT EXISTS ix_user_id ON "user" (id)'


def _validate_inputs(username: str, password: str) -> tuple[str, str]:
    normalized_username = str(username or "").strip()
    if not normalized_username:
        raise AuthConfigurationError("Admin username must be nonempty after trimming.")

    password_text = str(password or "")
    password_error = validate_password(password_text, password_text)
    if password_error:
        raise AuthConfigurationError(f"Admin password is invalid: {password_error}")
    return normalized_username, password_text


def _existing_user(connection: sqlite3.Connection, username_lower: str):
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'user'"
    ).fetchone()
    if table_exists is None:
        return None
    return connection.execute(
        'SELECT id, username FROM "user" WHERE username_lower = ?',
        (username_lower,),
    ).fetchone()


def _reject_existing_user(existing_user, *, force: bool) -> None:
    if existing_user is not None and not force:
        raise AuthConfigurationError(
            f'User "{existing_user[1]}" already exists. Rerun with --force to '
            "reset that user's password and grant administrator access."
        )


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def preflight_password_admin(
    *,
    database_path: Path,
    username: str,
    password: str,
    force: bool = False,
) -> None:
    """Validate credentials and force semantics without creating the database."""
    normalized_username, _password_text = _validate_inputs(username, password)
    database_path = Path(database_path)
    if not database_path.is_file():
        return

    connection = None
    try:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        existing_user = _existing_user(connection, normalized_username.lower())
    except (OSError, sqlite3.Error):
        raise AuthConfigurationError(PASSWORD_ADMIN_DATABASE_ERROR) from None
    finally:
        if connection is not None:
            connection.close()
    _reject_existing_user(existing_user, force=force)


def provision_password_admin(
    *,
    database_path: Path,
    username: str,
    password: str,
    force: bool = False,
) -> None:
    """Create or reset one admin in the explicit package-default SQLite DB."""
    normalized_username, password_text = _validate_inputs(username, password)
    database_path = Path(database_path)
    connection = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(_USER_TABLE_DDL)
        connection.execute(_USER_ID_INDEX_DDL)
        existing_user = _existing_user(connection, normalized_username.lower())
        _reject_existing_user(existing_user, force=force)
        password_hash = hash_password(password_text)
        if existing_user is None:
            connection.execute(
                'INSERT INTO "user" '
                "(id, username, username_lower, password, admin) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    normalized_username,
                    normalized_username.lower(),
                    password_hash,
                    1,
                ),
            )
        else:
            connection.execute(
                'UPDATE "user" SET password = ?, admin = 1 WHERE id = ?',
                (password_hash, existing_user[0]),
            )
        connection.commit()
    except AuthConfigurationError:
        _rollback(connection)
        raise
    except (OSError, sqlite3.Error):
        _rollback(connection)
        raise AuthConfigurationError(PASSWORD_ADMIN_DATABASE_ERROR) from None
    except Exception:
        _rollback(connection)
        raise
    finally:
        if connection is not None:
            connection.close()
