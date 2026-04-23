from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .paths import SlideRuntimePaths, SlideSessionPaths, get_slide_runtime_paths

SESSION_MODES = {"chat", "run"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default
        ),
    )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise ValueError(f"Session metadata in {path} must be a JSON object.")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file_obj:
        for raw_line in file_obj:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Transcript event in {path} must be a JSON object.")
            events.append(payload)
    return events


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    payload = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, default=_json_default)
        for record in records
    )
    if payload:
        payload += "\n"
    _atomic_write_text(path, payload)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in SESSION_MODES:
        raise ValueError(
            f"Unsupported session mode '{mode}'. Expected one of {sorted(SESSION_MODES)}."
        )
    return normalized


def _build_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _build_title(*, mode: str, title: str, prompt: str, input_path: str) -> str:
    explicit_title = title.strip()
    if explicit_title:
        return explicit_title

    prompt_title = " ".join(prompt.split()).strip()
    if prompt_title:
        return prompt_title[:80]

    if input_path:
        return Path(input_path).stem or f"{mode} session"

    return f"{mode} session"


@dataclass
class SlideSessionSummary:
    session_id: str
    mode: str
    title: str
    input_path: str
    prompt: str
    cwd: str
    status: str
    output_path: str
    created_at: str
    updated_at: str
    event_count: int
    session_dir: Path
    metadata_path: Path
    transcript_dir: Path
    transcript_path: Path
    artifacts_dir: Path
    patches_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "title": self.title,
            "input_path": self.input_path,
            "prompt": self.prompt,
            "cwd": self.cwd,
            "status": self.status,
            "output_path": self.output_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "event_count": self.event_count,
            "session_dir": str(self.session_dir),
            "metadata_path": str(self.metadata_path),
            "transcript_dir": str(self.transcript_dir),
            "transcript_path": str(self.transcript_path),
            "artifacts_dir": str(self.artifacts_dir),
            "patches_dir": str(self.patches_dir),
            "metadata": dict(self.metadata),
        }


@dataclass
class SlideSession(SlideSessionSummary):
    events: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload["events"] = [dict(event) for event in self.events]
        return payload


class SlideSessionStore:
    def __init__(
        self,
        *,
        base_dir: str | Path | None = None,
        runtime_paths: SlideRuntimePaths | None = None,
    ) -> None:
        self.runtime_paths = runtime_paths or get_slide_runtime_paths(base_dir=base_dir)
        self.runtime_paths.ensure_exists()

    @property
    def sessions_dir(self) -> Path:
        return self.runtime_paths.sessions_dir

    def create_session(
        self,
        *,
        mode: str,
        title: str = "",
        input_path: str = "",
        prompt: str = "",
        cwd: str = "",
        output_path: str = "",
        status: str = "created",
        metadata: Mapping[str, Any] | None = None,
        session_id: str | None = None,
    ) -> SlideSession:
        normalized_mode = _normalize_mode(mode)
        created_at = _utc_now_iso()
        resolved_session_id = session_id or _build_session_id()
        session_paths = self.runtime_paths.session_paths(
            resolved_session_id
        ).ensure_exists()

        if session_paths.metadata_path.exists():
            raise FileExistsError(f"Session '{resolved_session_id}' already exists.")

        session = SlideSession(
            session_id=resolved_session_id,
            mode=normalized_mode,
            title=_build_title(
                mode=normalized_mode,
                title=_coerce_text(title),
                prompt=_coerce_text(prompt),
                input_path=_coerce_text(input_path),
            ),
            input_path=_coerce_text(input_path),
            prompt=_coerce_text(prompt),
            cwd=_coerce_text(cwd),
            status=_coerce_text(status) or "created",
            output_path=_coerce_text(output_path),
            created_at=created_at,
            updated_at=created_at,
            event_count=0,
            session_dir=session_paths.session_dir,
            metadata_path=session_paths.metadata_path,
            transcript_dir=session_paths.transcript_dir,
            transcript_path=session_paths.transcript_path,
            artifacts_dir=session_paths.artifacts_dir,
            patches_dir=session_paths.patches_dir,
            metadata=dict(metadata or {}),
            events=[],
        )
        return self.persist_session(session)

    def persist_session(self, session: SlideSession) -> SlideSession:
        session_paths = self.runtime_paths.session_paths(
            session.session_id
        ).ensure_exists()
        existing_payload = (
            _read_json(session_paths.metadata_path)
            if session_paths.metadata_path.exists()
            else {}
        )
        created_at = (
            _coerce_text(session.created_at)
            or _coerce_text(existing_payload.get("created_at"))
            or _utc_now_iso()
        )
        updated_at = _coerce_text(session.updated_at) or _utc_now_iso()
        events = [dict(event) for event in session.events]

        stored = SlideSession(
            session_id=session.session_id,
            mode=_normalize_mode(session.mode),
            title=_build_title(
                mode=session.mode,
                title=_coerce_text(session.title),
                prompt=_coerce_text(session.prompt),
                input_path=_coerce_text(session.input_path),
            ),
            input_path=_coerce_text(session.input_path),
            prompt=_coerce_text(session.prompt),
            cwd=_coerce_text(session.cwd),
            status=_coerce_text(session.status) or "created",
            output_path=_coerce_text(session.output_path),
            created_at=created_at,
            updated_at=updated_at,
            event_count=len(events),
            session_dir=session_paths.session_dir,
            metadata_path=session_paths.metadata_path,
            transcript_dir=session_paths.transcript_dir,
            transcript_path=session_paths.transcript_path,
            artifacts_dir=session_paths.artifacts_dir,
            patches_dir=session_paths.patches_dir,
            metadata=dict(session.metadata or {}),
            events=events,
        )

        _write_json(stored.metadata_path, self._metadata_payload(stored))
        _write_jsonl(stored.transcript_path, stored.events)
        return stored

    def append_event(self, session_id: str, event: Mapping[str, Any]) -> SlideSession:
        session = self.load_session(session_id)
        if session is None:
            raise FileNotFoundError(f"Session '{session_id}' was not found.")

        event_payload = dict(event)
        event_payload.setdefault("timestamp", _utc_now_iso())
        session.events.append(event_payload)
        session.event_count = len(session.events)
        session.updated_at = (
            _coerce_text(event_payload.get("timestamp")) or _utc_now_iso()
        )

        with session.transcript_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(
                json.dumps(
                    event_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=_json_default,
                )
            )
            file_obj.write("\n")

        _write_json(session.metadata_path, self._metadata_payload(session))
        return session

    def list_sessions(
        self,
        *,
        mode: str | None = None,
        limit: int | None = None,
    ) -> list[SlideSessionSummary]:
        normalized_mode = _normalize_mode(mode) if mode is not None else None
        self.runtime_paths.ensure_exists()

        sessions: list[SlideSessionSummary] = []
        for metadata_path in self.sessions_dir.glob("*/session.json"):
            payload = _read_json(metadata_path)
            if normalized_mode is not None and payload.get("mode") != normalized_mode:
                continue
            session_id = (
                _coerce_text(payload.get("session_id")) or metadata_path.parent.name
            )
            session_paths = self.runtime_paths.session_paths(session_id).ensure_exists()
            sessions.append(self._summary_from_payload(payload, session_paths))

        sessions.sort(
            key=lambda item: (item.updated_at, item.created_at, item.session_id),
            reverse=True,
        )
        if limit is not None:
            return sessions[:limit]
        return sessions

    def load_session(self, session_id: str) -> SlideSession | None:
        session_paths = self.runtime_paths.session_paths(session_id)
        if not session_paths.metadata_path.exists():
            return None

        session_paths.ensure_exists()
        payload = _read_json(session_paths.metadata_path)
        events = _read_jsonl(session_paths.transcript_path)
        summary = self._summary_from_payload(
            payload, session_paths, event_count=len(events)
        )
        return SlideSession(
            session_id=summary.session_id,
            mode=summary.mode,
            title=summary.title,
            input_path=summary.input_path,
            prompt=summary.prompt,
            cwd=summary.cwd,
            status=summary.status,
            output_path=summary.output_path,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            event_count=summary.event_count,
            session_dir=summary.session_dir,
            metadata_path=summary.metadata_path,
            transcript_dir=summary.transcript_dir,
            transcript_path=summary.transcript_path,
            artifacts_dir=summary.artifacts_dir,
            patches_dir=summary.patches_dir,
            metadata=dict(summary.metadata),
            events=events,
        )

    def update_session(self, session_id: str, **changes: Any) -> SlideSession:
        session = self.load_session(session_id)
        if session is None:
            raise FileNotFoundError(f"Session '{session_id}' was not found.")

        for field_name, value in changes.items():
            if field_name == "session_id":
                raise ValueError("session_id cannot be updated in place.")
            if not hasattr(session, field_name):
                raise AttributeError(f"Unknown session field '{field_name}'.")
            setattr(session, field_name, value)

        session.updated_at = _utc_now_iso()
        return self.persist_session(session)

    def _summary_from_payload(
        self,
        payload: Mapping[str, Any],
        session_paths: SlideSessionPaths,
        *,
        event_count: int | None = None,
    ) -> SlideSessionSummary:
        normalized_mode = _normalize_mode(_coerce_text(payload.get("mode")))
        return SlideSessionSummary(
            session_id=_coerce_text(payload.get("session_id"))
            or session_paths.session_id,
            mode=normalized_mode,
            title=_build_title(
                mode=normalized_mode,
                title=_coerce_text(payload.get("title")),
                prompt=_coerce_text(payload.get("prompt")),
                input_path=_coerce_text(payload.get("input_path")),
            ),
            input_path=_coerce_text(payload.get("input_path")),
            prompt=_coerce_text(payload.get("prompt")),
            cwd=_coerce_text(payload.get("cwd")),
            status=_coerce_text(payload.get("status")) or "created",
            output_path=_coerce_text(payload.get("output_path")),
            created_at=_coerce_text(payload.get("created_at")) or _utc_now_iso(),
            updated_at=_coerce_text(payload.get("updated_at")) or _utc_now_iso(),
            event_count=int(
                event_count
                if event_count is not None
                else payload.get("event_count") or 0
            ),
            session_dir=session_paths.session_dir,
            metadata_path=session_paths.metadata_path,
            transcript_dir=session_paths.transcript_dir,
            transcript_path=session_paths.transcript_path,
            artifacts_dir=session_paths.artifacts_dir,
            patches_dir=session_paths.patches_dir,
            metadata=dict(payload.get("metadata") or {}),
        )

    def _metadata_payload(self, session: SlideSessionSummary) -> dict[str, Any]:
        return {
            "version": 1,
            "session_id": session.session_id,
            "mode": session.mode,
            "title": session.title,
            "input_path": session.input_path,
            "prompt": session.prompt,
            "cwd": session.cwd,
            "status": session.status,
            "output_path": session.output_path,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "event_count": session.event_count,
            "metadata": dict(session.metadata),
        }


__all__ = [
    "SESSION_MODES",
    "SlideSession",
    "SlideSessionStore",
    "SlideSessionSummary",
]
