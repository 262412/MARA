from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Mapping
from pathlib import Path

import pytest
from ktem.desktop_model_routes import (
    DesktopRouteMigrationError,
    prepare_desktop_model_routes,
)

SECRET = "desktop-route-secret-sentinel"


def _create_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            'CREATE TABLE llm_table (name TEXT PRIMARY KEY, spec JSON, "default" BOOLEAN)'
        )
        connection.execute(
            'CREATE TABLE embedding (name TEXT PRIMARY KEY, spec JSON, "default" BOOLEAN)'
        )
        connection.execute("CREATE TABLE user_record (value TEXT)")
        connection.execute("INSERT INTO user_record VALUES ('preserve-me')")


def _insert_route(
    database: Path,
    table: str,
    name: str,
    spec: Mapping[str, object],
    *,
    default: bool,
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            f'INSERT OR REPLACE INTO "{table}" (name, spec, "default") VALUES (?, ?, ?)',
            (name, json.dumps(spec), int(default)),
        )


def _settings(
    *,
    chat_name: str = "openai",
    chat_model: str = "gpt-5.6-luna",
    chat_base_url: str = "https://api.openai.com/v1",
    embedding_name: str = "openai",
    embedding_model: str = "text-embedding-3-small",
) -> dict[str, object]:
    return {
        "KH_LLMS": {
            chat_name: {
                "default": True,
                "spec": {
                    "__type__": "kotaemon.llms.ChatOpenAI",
                    "model": chat_model,
                    "base_url": chat_base_url,
                    "api_key": SECRET,
                },
            }
        },
        "KH_EMBEDDINGS": {
            embedding_name: {
                "default": True,
                "spec": {
                    "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                    "model": embedding_model,
                    "base_url": chat_base_url,
                    "api_key": SECRET,
                },
            }
        },
    }


def _rows(database: Path, table: str) -> list[tuple[str, dict[str, object], int]]:
    with sqlite3.connect(database) as connection:
        values = connection.execute(
            f'SELECT name, spec, "default" FROM "{table}" ORDER BY name'
        ).fetchall()
    return [(name, json.loads(spec), int(default)) for name, spec, default in values]


@pytest.mark.parametrize("reverse", [False, True])
def test_desktop_route_migration_replaces_stale_defaults_without_deleting_data(
    tmp_path: Path,
    reverse: bool,
) -> None:
    database = tmp_path / "state" / "ktem_app_data" / "user_data" / "sql.db"
    _create_database(database)
    legacy_routes = [
        (
            "google",
            {"__type__": "legacy.Google", "api_key": "old-google-secret"},
        ),
        (
            "openai",
            {
                "__type__": "kotaemon.llms.ChatOpenAI",
                "model": "legacy-chat-model",
                "base_url": "https://legacy.example/v1",
                "api_key": "old-openai-secret",
            },
        ),
    ]
    for name, spec in reversed(legacy_routes) if reverse else legacy_routes:
        _insert_route(database, "llm_table", name, spec, default=True)
    _insert_route(
        database,
        "embedding",
        "azure",
        {"__type__": "legacy.Azure", "api_key": "old-embedding-secret"},
        default=True,
    )

    identity = prepare_desktop_model_routes(
        _settings(),
        database_path=database,
        data_root=tmp_path,
        settings_revision="settings-revision-2",
    )
    prepare_desktop_model_routes(
        _settings(),
        database_path=database,
        data_root=tmp_path,
        settings_revision="settings-revision-2",
    )

    llm_rows = _rows(database, "llm_table")
    embedding_rows = _rows(database, "embedding")
    current_llm = next(row for row in llm_rows if row[0] == "openai")
    current_embedding = next(row for row in embedding_rows if row[0] == "openai")
    assert current_llm[1]["model"] == "gpt-5.6-luna"
    assert current_llm[1]["base_url"] == "https://api.openai.com/v1"
    assert current_llm[1]["secret_ref"] == "desktop-safe-storage:chat"
    assert current_embedding[1]["model"] == "text-embedding-3-small"
    assert current_embedding[1]["secret_ref"] == "desktop-safe-storage:embedding"
    assert sum(row[2] for row in llm_rows) == 1
    assert sum(row[2] for row in embedding_rows) == 1
    assert len(llm_rows) == 2
    assert len(embedding_rows) == 2
    assert all("api_key" not in row[1] for row in llm_rows + embedding_rows)
    assert identity.query_provider == "openai"
    assert identity.query_model == "gpt-5.6-luna"
    assert identity.settings_revision == "settings-revision-2"
    assert len(identity.route_fingerprint) == 64
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM user_record").fetchone() == (
            "preserve-me",
        )


def test_provider_round_trip_keeps_one_default_and_never_persists_credentials(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state" / "ktem_app_data" / "user_data" / "sql.db"
    _create_database(database)

    for revision, provider, model, endpoint in (
        ("revision-openai-1", "openai", "gpt-5.6-luna", "https://api.openai.com/v1"),
        ("revision-azure", "azure", "azure-deployment", "https://azure.example"),
        ("revision-ollama", "ollama", "llama3", "http://127.0.0.1:11434/v1"),
        ("revision-openai-2", "openai", "gpt-5.6-luna", "https://api.openai.com/v1"),
    ):
        settings = _settings(
            chat_name=provider,
            chat_model=model,
            chat_base_url=endpoint,
            embedding_name=provider,
            embedding_model=f"{model}-embedding",
        )
        prepare_desktop_model_routes(
            settings,
            database_path=database,
            data_root=tmp_path,
            settings_revision=revision,
        )
        assert sum(row[2] for row in _rows(database, "llm_table")) == 1
        assert sum(row[2] for row in _rows(database, "embedding")) == 1

    raw = database.read_bytes()
    assert SECRET.encode() not in raw
    assert b"old-openai-secret" not in raw


def test_secret_cleanup_covers_sqlite_sidecars_and_desktop_backups(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state" / "ktem_app_data" / "user_data" / "sql.db"
    _create_database(database)
    _insert_route(
        database,
        "llm_table",
        "openai",
        {"__type__": "legacy.OpenAI", "model": "old", "api_key": SECRET},
        default=True,
    )
    backup = tmp_path / "backups" / "sql.db"
    backup.parent.mkdir(parents=True)
    shutil.copy2(database, backup)
    database.with_name("sql.db-journal").write_bytes(SECRET.encode())

    prepare_desktop_model_routes(
        _settings(),
        database_path=database,
        data_root=tmp_path,
        settings_revision="settings-revision-clean",
    )

    checked = [database, backup, *database.parent.glob("sql.db-*")]
    assert checked
    for path in checked:
        assert SECRET.encode() not in path.read_bytes(), path.name


def test_locked_database_fails_closed_without_replacing_user_data(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state" / "ktem_app_data" / "user_data" / "sql.db"
    _create_database(database)
    _insert_route(
        database,
        "llm_table",
        "openai",
        {"__type__": "legacy.OpenAI", "model": "old", "api_key": SECRET},
        default=True,
    )
    blocker = sqlite3.connect(database)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(DesktopRouteMigrationError):
            prepare_desktop_model_routes(
                _settings(),
                database_path=database,
                data_root=tmp_path,
                settings_revision="settings-revision-locked",
            )
    finally:
        blocker.rollback()
        blocker.close()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM user_record").fetchone() == (
            "preserve-me",
        )
