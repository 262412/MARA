from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

DESKTOP_ROUTE_MIGRATION_VERSION = 1
_SAFE_REVISION = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_SQLITE_HEADER = b"SQLite format 3\x00"
_NON_SECRET_CREDENTIAL_VALUES = {
    "",
    "ollama",
    "your-key",
    "your_api_key",
    "your_key",
    "<your_openai_key>",
    "<your_openai_api_key>",
}


class DesktopRouteMigrationError(RuntimeError):
    """Fail-closed Desktop model route migration error."""


@dataclass(frozen=True)
class DesktopRouteIdentity:
    query_route_name: str
    query_provider: str
    query_model: str
    embedding_route_name: str
    embedding_provider: str
    embedding_model: str
    settings_revision: str
    sidecar_pid: int
    route_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_provider": self.query_provider,
            "query_model": self.query_model,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "settings_revision": self.settings_revision,
            "sidecar_pid": self.sidecar_pid,
            "route_fingerprint": self.route_fingerprint,
        }


def desktop_model_settings_enabled() -> bool:
    return str(
        os.environ.get("MARA_DESKTOP_MODEL_SETTINGS", "") or ""
    ).strip() == "1" and bool(
        str(os.environ.get("MARA_DESKTOP_DATA_DIR", "") or "").strip()
    )


def prepare_desktop_model_routes(
    settings: Mapping[str, Any] | object,
    *,
    database_path: Path | str | None = None,
    data_root: Path | str | None = None,
    settings_revision: str | None = None,
) -> DesktopRouteIdentity:
    """Canonicalize Desktop model tables without persisting runtime credentials."""
    revision = (
        settings_revision
        if settings_revision is not None
        else str(os.environ.get("MARA_DESKTOP_SETTINGS_REVISION", "") or "").strip()
    )
    if revision and not _SAFE_REVISION.fullmatch(revision):
        raise DesktopRouteMigrationError("Desktop model settings revision is invalid.")
    llm_configs = _settings_value(settings, "KH_LLMS")
    embedding_configs = _settings_value(settings, "KH_EMBEDDINGS")
    identity = _route_identity(llm_configs, embedding_configs, revision)
    resolved_database = _database_path(settings, database_path)
    resolved_root = _data_root(data_root)
    if resolved_database is not None and resolved_database.exists():
        try:
            secrets = _canonicalize_database(
                resolved_database,
                llm_configs=llm_configs,
                embedding_configs=embedding_configs,
            )
            _scrub_backup_databases(resolved_root, secrets)
            _verify_secret_absence(resolved_database, resolved_root, secrets)
        except DesktopRouteMigrationError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            raise DesktopRouteMigrationError(
                "Desktop model route migration could not be completed safely."
            ) from None
    if resolved_root is not None:
        _write_migration_marker(resolved_root, identity)
    return identity


def desktop_runtime_spec(
    settings: Mapping[str, Any] | object,
    kind: str,
    name: str,
) -> dict[str, Any] | None:
    key = "KH_LLMS" if kind == "chat" else "KH_EMBEDDINGS"
    configs = _settings_value(settings, key)
    config = configs.get(name)
    if not isinstance(config, Mapping) or not isinstance(config.get("spec"), Mapping):
        return None
    return _copy_json_value(config["spec"])


def persisted_desktop_spec(spec: Mapping[str, Any], kind: str) -> dict[str, Any]:
    sanitized = _sanitize_value(spec)
    if not isinstance(sanitized, dict):
        sanitized = {}
    provider = _provider_from_spec("", sanitized)
    if provider in {"openai", "azure"}:
        sanitized["secret_ref"] = f"desktop-safe-storage:{kind}"
    return sanitized


def _canonicalize_database(
    database_path: Path,
    *,
    llm_configs: Mapping[str, Any],
    embedding_configs: Mapping[str, Any],
) -> set[bytes]:
    secrets: set[bytes] = set()
    connection = sqlite3.connect(database_path, timeout=5)
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("BEGIN IMMEDIATE")
        _canonicalize_table(
            connection,
            "llm_table",
            llm_configs,
            kind="chat",
            secrets=secrets,
        )
        _canonicalize_table(
            connection,
            "embedding",
            embedding_configs,
            kind="embedding",
            secrets=secrets,
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("VACUUM")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    _remove_inactive_sqlite_sidecars(database_path)
    return secrets


def _canonicalize_table(
    connection: sqlite3.Connection,
    table_name: str,
    configs: Mapping[str, Any],
    *,
    kind: str,
    secrets: set[bytes],
) -> None:
    if not _table_exists(connection, table_name):
        return
    rows = connection.execute(f'SELECT name, spec FROM "{table_name}"').fetchall()
    for name, raw_spec in rows:
        spec = _load_spec(raw_spec)
        secrets.update(_secret_values(spec))
        connection.execute(
            f'UPDATE "{table_name}" SET spec = ?, "default" = 0 WHERE name = ?',
            (json.dumps(persisted_desktop_spec(spec, kind), sort_keys=True), name),
        )

    selected = _selected_config(configs)
    if selected is None:
        return
    name, config = selected
    raw_spec = config.get("spec")
    if not isinstance(raw_spec, Mapping):
        return
    secrets.update(_secret_values(raw_spec))
    persisted = persisted_desktop_spec(raw_spec, kind)
    connection.execute(
        f'INSERT INTO "{table_name}" (name, spec, "default") VALUES (?, ?, 1) '
        'ON CONFLICT(name) DO UPDATE SET spec = excluded.spec, "default" = 1',
        (name, json.dumps(persisted, sort_keys=True)),
    )


def _scrub_backup_databases(data_root: Path | None, secrets: set[bytes]) -> None:
    if data_root is None:
        return
    backup_root = data_root / "backups"
    if not backup_root.exists():
        return
    for candidate in sorted(path for path in backup_root.rglob("*") if path.is_file()):
        content = candidate.read_bytes()
        if not content.startswith(_SQLITE_HEADER):
            if any(secret in content for secret in secrets):
                raise DesktopRouteMigrationError(
                    "A Desktop backup still contains an unprotected model credential."
                )
            continue
        connection = sqlite3.connect(candidate, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")
            for table, kind in (("llm_table", "chat"), ("embedding", "embedding")):
                if not _table_exists(connection, table):
                    continue
                rows = connection.execute(
                    f'SELECT name, spec FROM "{table}"'
                ).fetchall()
                for name, raw_spec in rows:
                    spec = _load_spec(raw_spec)
                    secrets.update(_secret_values(spec))
                    connection.execute(
                        f'UPDATE "{table}" SET spec = ? WHERE name = ?',
                        (
                            json.dumps(
                                persisted_desktop_spec(spec, kind),
                                sort_keys=True,
                            ),
                            name,
                        ),
                    )
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        _remove_inactive_sqlite_sidecars(candidate)


def _verify_secret_absence(
    database_path: Path,
    data_root: Path | None,
    secrets: set[bytes],
) -> None:
    if not secrets:
        return
    candidates = [database_path, *database_path.parent.glob(f"{database_path.name}-*")]
    if data_root is not None and (data_root / "backups").exists():
        candidates.extend(
            path for path in (data_root / "backups").rglob("*") if path.is_file()
        )
    for candidate in candidates:
        content = candidate.read_bytes()
        if any(secret in content for secret in secrets):
            raise DesktopRouteMigrationError(
                "Desktop model credentials remain in a runtime database artifact."
            )


def _remove_inactive_sqlite_sidecars(database_path: Path) -> None:
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = database_path.with_name(f"{database_path.name}{suffix}")
        try:
            sidecar.unlink()
        except FileNotFoundError:
            pass


def _write_migration_marker(
    data_root: Path,
    identity: DesktopRouteIdentity,
) -> None:
    destination = data_root / "state" / "model-route-migration.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
    payload = {
        "version": DESKTOP_ROUTE_MIGRATION_VERSION,
        "settings_revision": identity.settings_revision,
        "route_fingerprint": identity.route_fingerprint,
    }
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _route_identity(
    llm_configs: Mapping[str, Any],
    embedding_configs: Mapping[str, Any],
    revision: str,
) -> DesktopRouteIdentity:
    chat_name, chat_spec = _selected_name_and_spec(llm_configs)
    embedding_name, embedding_spec = _selected_name_and_spec(embedding_configs)
    chat_provider = _provider_from_spec(chat_name, chat_spec)
    embedding_provider = _provider_from_spec(embedding_name, embedding_spec)
    chat_model = _model_from_spec(chat_spec)
    embedding_model = _model_from_spec(embedding_spec)
    canonical = {
        "chat": _fingerprint_route(chat_name, chat_provider, chat_model, chat_spec),
        "embedding": _fingerprint_route(
            embedding_name,
            embedding_provider,
            embedding_model,
            embedding_spec,
        ),
        "settings_revision": revision,
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DesktopRouteIdentity(
        query_route_name=chat_name,
        query_provider=chat_provider,
        query_model=chat_model,
        embedding_route_name=embedding_name,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        settings_revision=revision,
        sidecar_pid=os.getpid(),
        route_fingerprint=fingerprint,
    )


def _fingerprint_route(
    name: str,
    provider: str,
    model: str,
    spec: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "name": name,
        "provider": provider,
        "model": model,
        "base_url": str(spec.get("base_url") or spec.get("azure_endpoint") or ""),
        "api_version": str(spec.get("api_version") or ""),
        "type": str(spec.get("__type__") or ""),
    }


def _settings_value(
    settings: Mapping[str, Any] | object,
    name: str,
) -> Mapping[str, Any]:
    value = (
        settings.get(name)
        if isinstance(settings, Mapping)
        else getattr(settings, name, {})
    )
    return value if isinstance(value, Mapping) else {}


def _database_path(
    settings: Mapping[str, Any] | object,
    explicit: Path | str | None,
) -> Path | None:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    database_url = (
        settings.get("KH_DATABASE", "")
        if isinstance(settings, Mapping)
        else getattr(settings, "KH_DATABASE", "")
    )
    prefix = "sqlite:///"
    value = str(database_url or "")
    if not value.startswith(prefix):
        return None
    return Path(value[len(prefix) :]).expanduser().resolve()


def _data_root(explicit: Path | str | None) -> Path | None:
    value = (
        explicit if explicit is not None else os.environ.get("MARA_DESKTOP_DATA_DIR")
    )
    return Path(value).expanduser().resolve() if value else None


def _selected_config(
    configs: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]] | None:
    selected = [
        (str(name), config)
        for name, config in configs.items()
        if isinstance(config, Mapping)
        and isinstance(config.get("spec"), Mapping)
        and bool(config.get("default"))
    ]
    return selected[0] if len(selected) == 1 else None


def _selected_name_and_spec(
    configs: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]]:
    selected = _selected_config(configs)
    if selected is None:
        return "", {}
    name, config = selected
    spec = config.get("spec")
    return name, spec if isinstance(spec, Mapping) else {}


def _provider_from_spec(name: str, spec: Mapping[str, Any]) -> str:
    normalized = name.casefold()
    model_type = str(spec.get("__type__") or "").casefold()
    if normalized in {"openai", "azure", "ollama"}:
        return normalized
    if "azure" in model_type:
        return "azure"
    if "openai" in model_type:
        return "openai"
    return ""


def _model_from_spec(spec: Mapping[str, Any]) -> str:
    return str(spec.get("model") or spec.get("azure_deployment") or "").strip()


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_value(item)
            for key, item in value.items()
            if not _sensitive_key(str(key))
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _secret_values(value: Any) -> set[bytes]:
    values: set[bytes] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if (
                _sensitive_key(str(key))
                and isinstance(item, str)
                and len(item) >= 4
                and item.strip().casefold() not in _NON_SECRET_CREDENTIAL_VALUES
            ):
                values.add(item.encode("utf-8"))
            else:
                values.update(_secret_values(item))
    elif isinstance(value, list):
        for item in value:
            values.update(_secret_values(item))
    return values


def _sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return normalized != "secret_ref" and any(
        marker in normalized for marker in _SENSITIVE_KEY_MARKERS
    )


def _load_spec(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, Mapping) else {}
    return {}


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _copy_json_value(value: Any) -> Any:
    return json.loads(json.dumps(value))
