from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from ktem.docqa import DocQARuntime


_PLACEHOLDER_CREDENTIALS = {
    "",
    "<YOUR_OPENAI_KEY>",
    "your-key",
    "YOUR_API_KEY",
    "YOUR_KEY",
}


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def _extract_graph_source_ids(data_source: Any) -> list[str]:
    if not isinstance(data_source, dict):
        return []

    graph_source_ids = data_source.get("graph_source_ids", [])
    if isinstance(graph_source_ids, list):
        normalized_items = [
            str(item) for item in graph_source_ids if str(item or "").strip()
        ]
        if normalized_items:
            return normalized_items
    elif graph_source_ids not in (None, ""):
        return [str(graph_source_ids)]

    selected = data_source.get("selected", {})
    if not isinstance(selected, dict):
        return []

    output: list[str] = []
    for value in selected.values():
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            nested_values = candidate if isinstance(candidate, list) else [candidate]
            for nested in nested_values:
                if isinstance(nested, (dict, tuple, list)):
                    continue
                item = str(nested or "").strip()
                if not item or item.lower() in {"select", "upload", "all", "disabled"}:
                    continue
                if item not in output:
                    output.append(item)
    return output


def _load_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
    return {}


def _find_bundled_llama_index_nltk_cache() -> Path | None:
    for entry in sys.path:
        if not entry:
            continue
        candidate = (
            Path(entry).resolve() / "llama_index" / "core" / "_static" / "nltk_cache"
        )
        if candidate.is_dir():
            return candidate
    return None


def ensure_llama_index_nltk_cache() -> None:
    cache_dir = _find_bundled_llama_index_nltk_cache()
    if cache_dir is None:
        return

    os.environ.setdefault("NLTK_DATA", str(cache_dir))


def create_docqa_runtime() -> "DocQARuntime":
    ensure_llama_index_nltk_cache()
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.setdefault("GLOG_minloglevel", "3")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

    try:
        from cryptography.utils import CryptographyDeprecationWarning
    except Exception:
        CryptographyDeprecationWarning = Warning

    warnings.filterwarnings(
        "ignore",
        message=r"ARC4 has been moved.*",
        category=CryptographyDeprecationWarning,
    )
    from ktem.runtime_bootstrap import bootstrap_runtime_settings

    bootstrap_runtime_settings()
    from ktem.docqa import DocQARuntime

    return DocQARuntime()


def _resolve_default_user_id(flowsettings, engine, user_model) -> tuple[str, list[str]]:
    if not getattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT", False):
        return "default", []

    configured_username = str(
        getattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT_ADMIN", "admin") or "admin"
    ).strip()
    username_lookup = configured_username.lower()

    from sqlmodel import Session, select

    with Session(engine) as session:
        existing = session.exec(
            select(user_model).where(user_model.username_lower == username_lookup)
        ).first()
        if existing is not None:
            return str(existing.id), []

        fallback_admin = session.exec(
            select(user_model).where(user_model.admin.is_(True))
        ).first()
        if fallback_admin is not None:
            return str(fallback_admin.id), []

    return "", ["Default managed DocQA user does not exist yet."]


def _pick_default_model_name(
    configs: Any,
    *,
    label: str,
    issues: list[str],
    warnings: list[str],
) -> str:
    if not isinstance(configs, dict) or not configs:
        issues.append(f"No configured default {label} is available.")
        return ""

    selected_name = ""
    selected_spec: dict[str, Any] = {}

    for name, config in configs.items():
        if bool((config or {}).get("default", False)):
            selected_name = str(name)
            selected_spec = dict((config or {}).get("spec", {}) or {})
            break

    if not selected_name:
        first_name, first_config = next(iter(configs.items()))
        selected_name = str(first_name)
        selected_spec = dict((first_config or {}).get("spec", {}) or {})

    for key, value in selected_spec.items():
        if "key" not in str(key).lower():
            continue
        if str(value or "").strip() in _PLACEHOLDER_CREDENTIALS:
            warnings.append(
                f"Default {label} '{selected_name}' appears to use placeholder credentials."
            )
            break

    return selected_name


def _resolve_file_index_definition(
    flowsettings, engine
) -> tuple[str, int | None, bool, list[str]]:
    configured_name = ""
    configured_private = False
    for item in getattr(flowsettings, "KH_INDICES", []) or []:
        if str((item or {}).get("index_type", "")).endswith("FileIndex"):
            configured_name = str((item or {}).get("name", "") or "")
            configured_private = bool(
                ((item or {}).get("config", {}) or {}).get("private", False)
            )
            break

    from ktem.index.models import Index
    from sqlmodel import Session, select

    with Session(engine) as session:
        rows = session.exec(select(Index)).all()

    for row in rows:
        if str(getattr(row, "index_type", "")).endswith("FileIndex"):
            config = dict(getattr(row, "config", {}) or {})
            return (
                str(getattr(row, "name", "") or configured_name),
                int(getattr(row, "id", 0) or 0),
                bool(config.get("private", configured_private)),
                [],
            )

    issues: list[str] = ["No default FileIndex is available."]
    return configured_name, None, configured_private, issues


def _count_indexed_files(
    engine,
    *,
    index_id: int | None,
    private_index: bool,
    default_user_id: str,
) -> tuple[int, list[str]]:
    if index_id is None:
        return 0, []

    from sqlalchemy import inspect, text

    table_name = f"index__{index_id}__source"
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return 0, [f"Indexed file table '{table_name}' is missing."]

    query = f'SELECT COUNT(*) FROM "{table_name}"'
    params: dict[str, Any] = {}
    if private_index:
        if not default_user_id:
            return 0, ["Cannot inspect indexed files without a default DocQA user."]
        query += ' WHERE "user" = :user_id'
        params["user_id"] = default_user_id

    with engine.connect() as connection:
        count = int(connection.execute(text(query), params).scalar() or 0)
    return count, []


def _count_saved_sessions(
    engine, conversation_model, default_user_id: str
) -> tuple[int, list[str]]:
    from sqlmodel import Session, select

    try:
        with Session(engine) as session:
            statement = select(conversation_model)
            if default_user_id:
                statement = statement.where(
                    (conversation_model.user == default_user_id)
                    | conversation_model.is_public.is_(True)
                )
            rows = session.exec(statement).all()
        return len(rows), []
    except Exception as exc:
        return 0, [f"Unable to read saved sessions: {exc}"]


def collect_docqa_file_records() -> list[dict[str, Any]]:
    from ktem.db.models import User, engine
    from theflow.settings import settings as flowsettings

    default_user_id, _issues = _resolve_default_user_id(flowsettings, engine, User)
    (
        _index_name,
        index_id,
        private_index,
        _index_issues,
    ) = _resolve_file_index_definition(flowsettings, engine)

    if index_id is None:
        return []

    from sqlalchemy import inspect, text

    table_name = f"index__{index_id}__source"
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return []

    query = (
        f'SELECT "id", "name", "size", "path", "date_created", "note" '
        f'FROM "{table_name}"'
    )
    params: dict[str, Any] = {}
    if private_index:
        if not default_user_id:
            return []
        query += ' WHERE "user" = :user_id'
        params["user_id"] = default_user_id
    query += ' ORDER BY "date_created" DESC'

    with engine.connect() as connection:
        rows = list(connection.execute(text(query), params).mappings())

    records: list[dict[str, Any]] = []
    for row in rows:
        note = _load_json_dict(row.get("note"))
        records.append(
            {
                "file_id": str(row.get("id", "") or ""),
                "name": str(row.get("name", "") or ""),
                "size": int(row.get("size", 0) or 0),
                "tokens": int(note.get("tokens", 0) or 0),
                "loader": str(note.get("loader", "") or ""),
                "path": str(row.get("path", "") or ""),
                "date_created": _serialize_value(row.get("date_created")),
            }
        )
    return records


def collect_docqa_session_summaries() -> list[dict[str, Any]]:
    from ktem.db.models import Conversation, User, engine
    from sqlmodel import Session, select
    from theflow.settings import settings as flowsettings

    default_user_id, _issues = _resolve_default_user_id(flowsettings, engine, User)

    with Session(engine) as session:
        statement = select(Conversation)
        if default_user_id:
            statement = statement.where(
                (Conversation.user == default_user_id)
                | Conversation.is_public.is_(True)
            )
        statement = statement.order_by(Conversation.date_created.desc())  # type: ignore[attr-defined]
        rows = session.exec(statement).all()

    summaries: list[dict[str, Any]] = []
    for row in rows:
        data_source = dict(row.data_source or {})
        messages = list(data_source.get("messages", []) or [])
        graph_source_ids = _extract_graph_source_ids(data_source)
        summaries.append(
            {
                "conversation_id": row.id,
                "name": row.name,
                "message_count": len(messages),
                "graph_source_count": len(graph_source_ids),
                "origin": str(data_source.get("origin", "") or ""),
                "is_public": bool(row.is_public),
                "date_created": _serialize_value(row.date_created),
                "date_updated": _serialize_value(row.date_updated),
            }
        )
    return summaries


def collect_docqa_doctor_payload() -> dict[str, Any]:
    from ktem.runtime_bootstrap import (
        bootstrap_runtime_settings,
        describe_runtime_settings,
    )

    bootstrap_runtime_settings()
    runtime_settings = describe_runtime_settings()

    from ktem.db.models import Conversation, User, engine
    from theflow.settings import settings as flowsettings

    issues: list[str] = []
    warnings: list[str] = []

    default_user_id, user_issues = _resolve_default_user_id(flowsettings, engine, User)
    issues.extend(user_issues)

    index_name, index_id, private_index, index_issues = _resolve_file_index_definition(
        flowsettings, engine
    )
    issues.extend(index_issues)

    llm_default = _pick_default_model_name(
        getattr(flowsettings, "KH_LLMS", {}),
        label="LLM",
        issues=issues,
        warnings=warnings,
    )
    embedding_default = _pick_default_model_name(
        getattr(flowsettings, "KH_EMBEDDINGS", {}),
        label="embedding model",
        issues=issues,
        warnings=warnings,
    )

    file_count, file_issues = _count_indexed_files(
        engine,
        index_id=index_id,
        private_index=private_index,
        default_user_id=default_user_id,
    )
    issues.extend(file_issues)

    session_count, session_issues = _count_saved_sessions(
        engine,
        Conversation,
        default_user_id,
    )
    issues.extend(session_issues)

    graph_cache_dir = str(
        Path(
            getattr(
                flowsettings, "KH_APP_DATA_DIR", runtime_settings.get("data_dir", "")
            )
        )
        / "knowledge_graph"
        / "conversations"
    )

    return {
        "ok": not issues,
        "app_name": str(getattr(flowsettings, "KH_APP_NAME", "Kotaemon")),
        "default_user_id": default_user_id,
        "index_name": index_name,
        "index_id": index_id,
        "llm_default": llm_default,
        "embedding_default": embedding_default,
        "file_count": file_count,
        "session_count": session_count,
        "graph_cache_dir": graph_cache_dir,
        "issues": issues,
        "warnings": warnings,
    }


def parse_graph_context_file(graph_context_file: str) -> dict[str, Any]:
    if not graph_context_file:
        return {}

    with Path(graph_context_file).open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if not isinstance(payload, dict):
        raise click.ClickException("--graph-context-file must contain a JSON object.")
    return payload


def _extract_json_payload(raw_output: str) -> dict[str, Any]:
    lines = [line for line in str(raw_output or "").splitlines() if line.strip()]
    decoder = json.JSONDecoder()
    errors: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            continue
        payload = "\n".join(lines[index:])
        try:
            parsed, _offset = decoder.raw_decode(payload)
            if isinstance(parsed, dict):
                return parsed
            return {"payload": parsed}
        except JSONDecodeError as exc:
            errors.append(f"line {index + 1}: {exc}")
    raise RuntimeError(
        "Unable to parse JSON payload from acceptance output.\n"
        f"Errors: {errors}\n"
        f"Raw output:\n{raw_output}"
    )


def run_docqa_acceptance_matrix(
    *, keep_artifacts: bool = False, verbose: bool = False
) -> dict[str, Any]:
    command = [sys.executable, "-m", "ktem.docqa.acceptance"]
    if keep_artifacts:
        command.append("--keep-artifacts")
    if verbose:
        command.append("--verbose")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    try:
        payload = _extract_json_payload(completed.stdout)
    except RuntimeError:
        if completed.returncode != 0:
            raise RuntimeError(
                "DocQA acceptance matrix failed before emitting structured output.\n"
                f"STDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            ) from None
        raise

    if completed.returncode != 0 or payload.get("status") != "pass":
        details = [str(payload.get("error") or "DocQA acceptance matrix failed.")]
        if payload.get("work_dir"):
            details.append(f"Artifacts: {payload['work_dir']}")
        if payload.get("partial_results"):
            details.append(
                f"Completed checks: {len(payload.get('partial_results', []))}"
            )
        stderr_tail = str(payload.get("captured_stderr_tail") or "").strip()
        if stderr_tail:
            details.append(f"Captured stderr tail:\n{stderr_tail}")
        elif completed.stderr.strip():
            details.append(f"STDERR:\n{completed.stderr.strip()}")
        raise RuntimeError("\n".join(details))

    return payload


__all__ = [
    "collect_docqa_doctor_payload",
    "collect_docqa_file_records",
    "collect_docqa_session_summaries",
    "create_docqa_runtime",
    "ensure_llama_index_nltk_cache",
    "parse_graph_context_file",
    "run_docqa_acceptance_matrix",
]
