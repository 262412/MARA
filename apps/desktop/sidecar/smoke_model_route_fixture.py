from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

LEGACY_SECRET_SENTINEL = "mara-desktop-legacy-secret-sentinel"


def seed_legacy_model_routes(data_root: Path) -> Path:
    database = _database_path(data_root)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS llm_table "
            '(name TEXT PRIMARY KEY, spec JSON, "default" BOOLEAN)'
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS embedding "
            '(name TEXT PRIMARY KEY, spec JSON, "default" BOOLEAN)'
        )
        connection.execute(
            'INSERT OR REPLACE INTO llm_table (name, spec, "default") '
            "VALUES (?, ?, 1)",
            (
                "google",
                json.dumps(
                    {
                        "__type__": "legacy.GoogleChat",
                        "model": "legacy-google-model",
                        "api_key": LEGACY_SECRET_SENTINEL,
                    }
                ),
            ),
        )
        connection.execute(
            'INSERT OR REPLACE INTO llm_table (name, spec, "default") '
            "VALUES (?, ?, 1)",
            (
                "ollama",
                json.dumps(
                    {
                        "__type__": "kotaemon.llms.ChatOpenAI",
                        "model": "legacy-chat-model",
                        "base_url": "http://127.0.0.1:9/v1",
                        "api_key": LEGACY_SECRET_SENTINEL,
                    }
                ),
            ),
        )
        connection.execute(
            'INSERT OR REPLACE INTO embedding (name, spec, "default") '
            "VALUES (?, ?, 1)",
            (
                "azure",
                json.dumps(
                    {
                        "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
                        "azure_deployment": "legacy-embedding",
                        "azure_endpoint": "https://legacy.example",
                        "api_key": LEGACY_SECRET_SENTINEL,
                    }
                ),
            ),
        )
    return database


def verify_migrated_model_routes(
    data_root: Path,
    *,
    expected_chat_model: str,
    forbidden_secrets: tuple[str, ...] = (),
) -> dict[str, Any]:
    database = _database_path(data_root)
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        llm_rows = connection.execute(
            'SELECT name, spec, "default" FROM llm_table ORDER BY name'
        ).fetchall()
        embedding_rows = connection.execute(
            'SELECT name, spec, "default" FROM embedding ORDER BY name'
        ).fetchall()
    llm_defaults = [row for row in llm_rows if bool(row[2])]
    embedding_defaults = [row for row in embedding_rows if bool(row[2])]
    if len(llm_defaults) != 1 or len(embedding_defaults) != 1:
        raise RuntimeError("Desktop route migration did not produce unique defaults.")
    llm_spec = _spec(llm_defaults[0][1])
    if llm_spec.get("model") != expected_chat_model:
        raise RuntimeError("Desktop route migration kept the wrong chat model.")
    for _name, raw_spec, _default in [*llm_rows, *embedding_rows]:
        if _contains_sensitive_key(_spec(raw_spec)):
            raise RuntimeError("Desktop route migration persisted a model credential.")
    artifacts = [database, *database.parent.glob(f"{database.name}-*")]
    backup_root = data_root / "backups"
    if backup_root.exists():
        artifacts.extend(path for path in backup_root.rglob("*") if path.is_file())
    sentinel = LEGACY_SECRET_SENTINEL.encode("utf-8")
    if any(sentinel in path.read_bytes() for path in artifacts):
        raise RuntimeError("Desktop route migration left a plaintext model credential.")
    forbidden = tuple(
        value.encode("utf-8")
        for value in (LEGACY_SECRET_SENTINEL, *forbidden_secrets)
        if value
    )
    for path in (
        candidate for candidate in data_root.rglob("*") if candidate.is_file()
    ):
        content = path.read_bytes()
        if any(secret in content for secret in forbidden):
            raise RuntimeError("Desktop data contains a plaintext model credential.")
    marker = json.loads(
        (data_root / "state" / "model-route-migration.json").read_text(encoding="utf-8")
    )
    if marker.get("version") != 1 or len(str(marker.get("route_fingerprint"))) != 64:
        raise RuntimeError("Desktop route migration marker is invalid.")
    return {
        "chat_default": str(llm_defaults[0][0]),
        "chat_model": str(llm_spec["model"]),
        "embedding_default": str(embedding_defaults[0][0]),
        "route_fingerprint": str(marker["route_fingerprint"]),
        "settings_revision": str(marker.get("settings_revision") or ""),
        "plaintext_secret_absent": True,
    }


def _database_path(data_root: Path) -> Path:
    return (
        data_root.expanduser().resolve()
        / "state"
        / "ktem_app_data"
        / "user_data"
        / "sql.db"
    )


def _spec(value: Any) -> dict[str, Any]:
    loaded = json.loads(value) if isinstance(value, str) else value
    return dict(loaded) if isinstance(loaded, dict) else {}


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (
                key != "secret_ref"
                and any(
                    marker in key.casefold()
                    for marker in ("api_key", "token", "password", "credential")
                )
            )
            or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed or verify stale Desktop model route smoke data."
    )
    parser.add_argument("--data-root", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--seed", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-chat-model", default="")
    parser.add_argument("--forbidden-secret", action="append", default=[])
    arguments = parser.parse_args()
    if arguments.seed:
        seed_legacy_model_routes(arguments.data_root)
        return 0
    if not arguments.expected_chat_model:
        parser.error("--expected-chat-model is required with --verify")
    report = verify_migrated_model_routes(
        arguments.data_root,
        expected_chat_model=arguments.expected_chat_model,
        forbidden_secrets=tuple(arguments.forbidden_secret),
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
