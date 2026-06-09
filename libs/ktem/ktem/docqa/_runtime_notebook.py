from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktem.db.models import Conversation, engine
from sqlmodel import Session, select

from . import artifact_service as artifact_records
from .artifact_models import (
    ARTIFACT_STATUS_READY,
    build_artifact_record,
    normalize_artifact,
)

NOTEBOOK_KEY = "mara_notebook"
_SAFE_PATH_PART_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _timestamp(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat()


def _unique_text(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    result: list[str] = []
    seen: set[str] = set()
    for value in items:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _record_value(record: Any, key: str, default: Any = "") -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _topics_from_name(name: str) -> list[str]:
    stem = Path(str(name or "source")).stem
    topics = [
        part
        for part in _SAFE_PATH_PART_RE.split(stem.replace("_", " "))
        if part and not part.isdigit()
    ]
    return topics[:5] or [stem or "source"]


def _title_from_text(title: str | None, text: str) -> str:
    normalized = str(title or "").strip()
    if normalized:
        return normalized
    first_line = str(text or "").strip().splitlines()[0:1]
    return first_line[0][:80] if first_line else "Untitled note"


def _safe_path_part(value: str, fallback: str) -> str:
    normalized = _SAFE_PATH_PART_RE.sub("-", str(value or "").strip()).strip(".-")
    return (normalized or fallback)[:80]


def _normalize_note(note: Any) -> dict[str, Any] | None:
    if not isinstance(note, dict):
        return None
    text = str(note.get("text") or "").strip()
    if not text:
        return None
    created_at = str(note.get("created_at") or "").strip()
    updated_at = str(note.get("updated_at") or created_at).strip()
    normalized = {
        "note_id": str(note.get("note_id") or uuid.uuid4().hex),
        "title": _title_from_text(str(note.get("title") or ""), text),
        "text": text,
        "source": str(note.get("source") or "manual"),
        "citation_refs": _unique_text(note.get("citation_refs", [])),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    indexed_ids = _unique_text(note.get("indexed_source_ids", []))
    indexed_path = str(note.get("indexed_source_path") or "").strip()
    indexed_at = str(note.get("indexed_at") or "").strip()
    if indexed_ids:
        normalized["indexed_source_ids"] = indexed_ids
    if indexed_path:
        normalized["indexed_source_path"] = indexed_path
    if indexed_at:
        normalized["indexed_at"] = indexed_at
    return normalized


def _notebook(data_source: dict[str, Any] | None) -> dict[str, Any]:
    source = data_source if isinstance(data_source, dict) else {}
    raw = source.get(NOTEBOOK_KEY, {})
    raw = raw if isinstance(raw, dict) else {}
    notes = [
        note
        for note in (_normalize_note(item) for item in raw.get("notes", []))
        if note is not None
    ]
    artifacts = [
        artifact
        for artifact in (normalize_artifact(item) for item in raw.get("artifacts", []))
        if artifact is not None
    ]
    return {
        "selected_source_ids": _unique_text(
            raw.get("selected_source_ids", source.get("graph_source_ids", []))
        ),
        "notes": notes,
        "artifacts": artifacts,
    }


def _with_notebook(
    data_source: dict[str, Any] | None,
    notebook: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(data_source if isinstance(data_source, dict) else {})
    updated[NOTEBOOK_KEY] = notebook
    return updated


def set_selected_sources(
    data_source: dict[str, Any] | None,
    source_ids: list[str],
) -> dict[str, Any]:
    notebook = _notebook(data_source)
    selected = _unique_text(source_ids)
    notebook["selected_source_ids"] = selected
    updated = _with_notebook(data_source, notebook)
    updated["graph_source_ids"] = list(selected)
    return updated


def note_source_markdown(conversation_id: str, note: dict[str, Any]) -> str:
    title = _title_from_text(str(note.get("title") or ""), str(note.get("text") or ""))
    citation_refs = _unique_text(note.get("citation_refs", []))
    metadata = [
        f"Conversation: {conversation_id}",
        f"Note ID: {note.get('note_id', '')}",
        f"Source: {note.get('source', '')}",
        "Citation refs: " + (", ".join(citation_refs) if citation_refs else "(none)"),
    ]
    return "\n".join(
        [
            f"# {title}",
            "",
            *metadata,
            "",
            str(note.get("text") or "").strip(),
            "",
        ]
    )


def default_note_sources_dir() -> Path:
    from theflow.settings import settings as flowsettings

    return Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd())) / "mara_notes"


def materialize_note_source(
    conversation_id: str,
    note: dict[str, Any],
    root_dir: str | Path | None = None,
) -> str:
    source_root = Path(root_dir) if root_dir is not None else default_note_sources_dir()
    conversation_part = _safe_path_part(conversation_id, "conversation")
    note_part = _safe_path_part(str(note.get("note_id") or ""), "note")
    source_path = source_root / conversation_part / f"mara-note-{note_part}.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        note_source_markdown(conversation_id, note), encoding="utf-8"
    )
    return source_path.resolve().as_posix()


def record_note_indexed_source(
    data_source: dict[str, Any] | None,
    note_id: str,
    *,
    source_ids: list[str],
    source_path: str,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lookup = str(note_id or "").strip()
    notebook = _notebook(data_source)
    indexed_ids = _unique_text(source_ids)
    updated_note: dict[str, Any] | None = None
    notes: list[dict[str, Any]] = []
    for note in notebook["notes"]:
        if note["note_id"] == lookup:
            updated_note = {
                **note,
                "indexed_source_ids": indexed_ids,
                "indexed_source_path": str(source_path or "").strip(),
                "indexed_at": _timestamp(timestamp),
            }
            notes.append(updated_note)
        else:
            notes.append(note)
    if updated_note is None:
        raise ValueError(f"Note '{note_id}' does not exist.")

    notebook["notes"] = notes
    if indexed_ids:
        notebook["selected_source_ids"] = _unique_text(
            [*notebook["selected_source_ids"], *indexed_ids]
        )
    updated = _with_notebook(data_source, notebook)
    if indexed_ids:
        updated["graph_source_ids"] = list(notebook["selected_source_ids"])
    return updated, updated_note


def build_source_guides(records: list[Any]) -> list[dict[str, Any]]:
    guides: list[dict[str, Any]] = []
    for record in records:
        name = str(_record_value(record, "name", "source") or "source")
        tokens = int(_record_value(record, "tokens", 0) or 0)
        loader = str(_record_value(record, "loader", "document") or "document")
        metadata = {
            "tokens": tokens,
            "size": int(_record_value(record, "size", 0) or 0),
            "loader": loader,
            "path": str(_record_value(record, "path", "") or ""),
            "date_created": _record_value(record, "date_created", ""),
        }
        guides.append(
            {
                "source_id": str(_record_value(record, "file_id", "") or ""),
                "name": name,
                "summary": (
                    f"{name} is an indexed {loader} source with {tokens} tokens."
                ),
                "key_topics": _topics_from_name(name),
                "suggested_questions": [
                    f"What are the key points in {name}?",
                    f"Which evidence from {name} supports the answer?",
                ],
                "metadata": metadata,
            }
        )
    return guides


def list_notes(data_source: dict[str, Any] | None) -> list[dict[str, Any]]:
    return deepcopy(_notebook(data_source)["notes"])


def add_note(
    data_source: dict[str, Any] | None,
    *,
    text: str,
    title: str = "",
    source: str = "manual",
    citation_refs: list[str] | None = None,
    note_id: str | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = _timestamp(timestamp)
    note = {
        "note_id": note_id or uuid.uuid4().hex,
        "title": _title_from_text(title, text),
        "text": str(text or "").strip(),
        "source": str(source or "manual"),
        "citation_refs": _unique_text(citation_refs or []),
        "created_at": now,
        "updated_at": now,
    }
    notebook = _notebook(data_source)
    notebook["notes"] = [*notebook["notes"], note]
    return _with_notebook(data_source, notebook), note


def save_answer_as_note(
    data_source: dict[str, Any] | None,
    *,
    answer: str,
    title: str = "",
    citation_refs: list[str] | None = None,
    note_id: str | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return add_note(
        data_source,
        title=title,
        text=answer,
        source="answer",
        citation_refs=citation_refs,
        note_id=note_id,
        timestamp=timestamp,
    )


def save_artifact(
    data_source: dict[str, Any] | None,
    *,
    artifact_type: str,
    payload: Any,
    artifact_id: str | None = None,
    title: str = "",
    status: str = ARTIFACT_STATUS_READY,
    prompt: str = "",
    source_scope: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
    exports: list[dict[str, Any]] | None = None,
    generation: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = build_artifact_record(
        artifact_type=artifact_type,
        payload=payload,
        artifact_id=artifact_id,
        title=title,
        status=status,
        prompt=prompt,
        source_scope=source_scope,
        citations=citations,
        exports=exports,
        generation=generation,
        timestamp=timestamp,
    )
    notebook = _notebook(data_source)
    records = notebook["artifacts"]
    notebook["artifacts"], saved_artifact = artifact_records.append_artifact_record(
        records, artifact
    )
    return _with_notebook(data_source, notebook), saved_artifact


def list_artifacts(data_source: dict[str, Any] | None) -> list[dict[str, Any]]:
    return artifact_records.list_artifact_records(_notebook(data_source)["artifacts"])


def get_artifact(
    data_source: dict[str, Any] | None,
    artifact_id: str,
) -> dict[str, Any] | None:
    records = _notebook(data_source)["artifacts"]
    return artifact_records.get_artifact_record(records, artifact_id)


def delete_artifact(
    data_source: dict[str, Any] | None,
    artifact_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    notebook = _notebook(data_source)
    records = notebook["artifacts"]
    kept, deleted = artifact_records.delete_artifact_record(records, artifact_id)
    notebook["artifacts"] = kept
    return _with_notebook(data_source, notebook), deleted


def record_artifact_export(
    data_source: dict[str, Any] | None,
    artifact_id: str,
    *,
    export_format: str,
    path: str,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    notebook = _notebook(data_source)
    export_record = {
        "format": str(export_format or "").strip(),
        "path": str(path or "").strip(),
        "created_at": _timestamp(timestamp),
    }
    records = notebook["artifacts"]
    artifacts, updated_artifact = artifact_records.record_artifact_export_record(
        records, artifact_id, export_record
    )
    notebook["artifacts"] = artifacts
    return _with_notebook(data_source, notebook), updated_artifact


def save_artifact_to_conversation(
    conversation_id: str,
    *,
    artifact_type: str,
    payload: Any,
    artifact_id: str | None = None,
    title: str = "",
    status: str = ARTIFACT_STATUS_READY,
    prompt: str = "",
    source_scope: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
    exports: list[dict[str, Any]] | None = None,
    generation: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, artifact = save_artifact(
            dict(row.data_source or {}),
            artifact_type=artifact_type,
            payload=payload,
            artifact_id=artifact_id,
            title=title,
            status=status,
            prompt=prompt,
            source_scope=source_scope,
            citations=citations,
            exports=exports,
            generation=generation,
            timestamp=timestamp,
        )
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return artifact


def delete_artifact_from_conversation(
    conversation_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, artifact = delete_artifact(dict(row.data_source or {}), artifact_id)
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return artifact


def record_artifact_export_to_conversation(
    conversation_id: str,
    artifact_id: str,
    *,
    export_format: str,
    path: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, artifact = record_artifact_export(
            dict(row.data_source or {}),
            artifact_id,
            export_format=export_format,
            path=path,
            timestamp=timestamp,
        )
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return artifact


def save_captured_artifact(
    conversation_id: str,
    artifact: Any,
    **metadata: Any,
) -> dict[str, Any] | None:
    if artifact is None:
        return None
    artifact_type = str(metadata.pop("artifact_type", "") or "artifact")
    if isinstance(artifact, dict):
        artifact_type = str(artifact.get("type") or artifact_type)
        if isinstance(artifact.get("citations"), list):
            metadata.setdefault("citations", artifact.get("citations"))
    return save_artifact_to_conversation(
        conversation_id,
        artifact_type=artifact_type,
        payload=artifact,
        **metadata,
    )


def preserve_state(
    updated_data_source: dict[str, Any],
    existing_data_source: dict[str, Any] | None,
) -> dict[str, Any]:
    notebook = _notebook(existing_data_source)
    if not (
        notebook["selected_source_ids"] or notebook["notes"] or notebook["artifacts"]
    ):
        return updated_data_source
    merged = deepcopy(updated_data_source)
    merged[NOTEBOOK_KEY] = notebook
    return merged


def _load_conversation(session: Session, conversation_id: str) -> Conversation:
    row = session.exec(
        select(Conversation).where(Conversation.id == conversation_id)
    ).one_or_none()
    if row is None:
        raise ValueError(f"Conversation '{conversation_id}' does not exist.")
    return row


def get_notebook(conversation_id: str) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        return _notebook(dict(row.data_source or {}))


def add_note_to_conversation(
    conversation_id: str,
    *,
    title: str,
    text: str,
    note_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, note = add_note(
            dict(row.data_source or {}),
            title=title,
            text=text,
            note_id=note_id,
            timestamp=timestamp,
        )
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return note


def save_answer_note_to_conversation(
    conversation_id: str,
    *,
    title: str,
    answer: str,
    citation_refs: list[str] | None = None,
    note_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, note = save_answer_as_note(
            dict(row.data_source or {}),
            answer=answer,
            title=title,
            citation_refs=citation_refs,
            note_id=note_id,
            timestamp=timestamp,
        )
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return note


def select_conversation_sources(
    conversation_id: str,
    source_ids: list[str],
) -> list[str]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated = set_selected_sources(dict(row.data_source or {}), source_ids)
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return list(updated[NOTEBOOK_KEY]["selected_source_ids"])


def record_note_indexed_source_to_conversation(
    conversation_id: str,
    note_id: str,
    *,
    source_ids: list[str],
    source_path: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        row = _load_conversation(session, conversation_id)
        updated, note = record_note_indexed_source(
            dict(row.data_source or {}),
            note_id,
            source_ids=source_ids,
            source_path=source_path,
            timestamp=timestamp,
        )
        row.data_source = updated
        row.date_updated = datetime.now()
        session.add(row)
        session.commit()
        return note
