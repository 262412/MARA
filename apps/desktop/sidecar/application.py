from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from .api_errors import SidecarApiError
from .indexing_readiness import (
    DesktopIndexingPreflightError,
    IndexingReadiness,
    collect_indexing_readiness,
    index_failure_from_result,
    index_result_name,
    validate_index_sources,
)
from .model_routes import (
    apply_route_identity,
    prepare_model_routes,
    query_route_diagnostics,
    query_route_name,
)
from .query_commit_state import recover_committed_answer, state_with_query_commit_marker
from .query_readiness import QueryReadiness, collect_query_readiness
from .query_terminal_outcome import response_terminal_commit

FILE_RESPONSE_FIELDS = (
    "file_id",
    "name",
    "size",
    "tokens",
    "loader",
    "date_created",
)


def _collect_doctor() -> dict[str, Any]:
    from slide_cli.docqa_runtime import collect_docqa_doctor_payload

    return collect_docqa_doctor_payload()


def _collect_files() -> list[dict[str, Any]]:
    from slide_cli.docqa_runtime import collect_docqa_file_records

    return collect_docqa_file_records()


def _collect_sessions() -> list[dict[str, Any]]:
    from slide_cli.docqa_runtime import collect_docqa_session_summaries

    return collect_docqa_session_summaries()


def _collect_import_capabilities() -> dict[str, list[str]]:
    from slide_cli.docqa_runtime import collect_docqa_import_capabilities

    return collect_docqa_import_capabilities()


def _create_runtime() -> Any:
    from slide_cli.docqa_runtime import create_docqa_runtime

    return create_docqa_runtime(
        include_query_features=True,
        include_file_artifacts=False,
        reasoning_paths=("ktem.reasoning.simple.FullQAPipeline",),
    )


def _create_query_request(**values: Any) -> Any:
    from ktem.docqa import DocQARequest

    return DocQARequest(**values)


class DesktopFileNotFoundError(LookupError):
    pass


class DesktopSessionNotFoundError(LookupError):
    pass


class DesktopMutationError(RuntimeError):
    pass


class DesktopQueryPreflightError(SidecarApiError):
    @classmethod
    def from_readiness(cls, readiness: QueryReadiness) -> "DesktopQueryPreflightError":
        status_code = 503 if readiness.query_retryable else 409
        return cls(
            status_code,
            readiness.query_issue_code or "llm_not_configured",
            readiness.query_message,
            retryable=readiness.query_retryable,
        )


class DesktopApplicationService:
    def __init__(
        self,
        *,
        collect_doctor: Callable[[], dict[str, Any]] = _collect_doctor,
        collect_files: Callable[[], list[dict[str, Any]]] = _collect_files,
        collect_sessions: Callable[[], list[dict[str, Any]]] = _collect_sessions,
        collect_import_capabilities: Callable[
            [], dict[str, list[str]]
        ] = _collect_import_capabilities,
        collect_indexing_readiness: Callable[
            [], IndexingReadiness
        ] = collect_indexing_readiness,
        collect_query_readiness: Callable[[], QueryReadiness | None] = (
            collect_query_readiness
        ),
        create_runtime: Callable[[], Any] = _create_runtime,
        create_query_request: Callable[..., Any] = _create_query_request,
        prepare_model_routes: Callable[[], Any | None] = prepare_model_routes,
    ) -> None:
        self._collect_doctor = collect_doctor
        self._collect_files = collect_files
        self._collect_sessions = collect_sessions
        self._collect_import_capabilities = collect_import_capabilities
        self._collect_indexing_readiness = collect_indexing_readiness
        self._collect_query_readiness = collect_query_readiness
        self._create_runtime = create_runtime
        self._create_query_request = create_query_request
        self._prepare_model_routes = prepare_model_routes
        self._route_identity: Any | None = None
        self._routes_prepared = False
        self._runtime: Any | None = None
        self._runtime_lock = threading.Lock()

    def get_doctor(self) -> dict[str, Any]:
        with self._runtime_lock:
            identity = self._ensure_model_routes()
            doctor = self._collect_doctor()
            readiness = self._collect_indexing_readiness()
            query_readiness = self._collect_query_readiness()
        payload = {**doctor, **readiness.as_dict()}
        if query_readiness is not None:
            payload.update(query_readiness.as_dict())
        return apply_route_identity(payload, identity)

    def list_files(self) -> list[dict[str, Any]]:
        with self._runtime_lock:
            return [
                {field: record.get(field) for field in FILE_RESPONSE_FIELDS}
                for record in self._collect_files()
            ]

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._runtime_lock:
            return self._collect_sessions()

    def get_session(self, conversation_id: str) -> dict[str, Any]:
        with self._runtime_lock:
            session = self._get_runtime().load_session(conversation_id)
        if session is None:
            raise DesktopSessionNotFoundError(conversation_id)
        return _session_detail(session)

    def create_session(self) -> dict[str, Any]:
        with self._runtime_lock:
            session = self._get_runtime().create_session()
        return _session_detail(session)

    def stream_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
        cancel_event: threading.Event | None = None,
        *,
        turn_id: str = "",
    ) -> Iterator[dict[str, Any]]:
        with self._runtime_lock:
            identity = self._ensure_model_routes()
            source_records = _selected_source_records(
                self._collect_files(),
                selected_file_ids,
            )
            source_names = {
                str(record["file_id"]): str(record["name"]) for record in source_records
            }
            runtime = self._create_runtime()
            session = runtime.load_session(conversation_id)
            if session is None:
                raise DesktopSessionNotFoundError(conversation_id)
            request_state = state_with_query_commit_marker(session, turn_id)
            request = self._create_query_request(
                prompt=prompt,
                conversation_id=conversation_id,
                selected_file_ids=list(selected_file_ids),
                source_identity_crosswalk=_source_identity_crosswalk(source_records),
                qa_scope=(
                    "document" if len(selected_file_ids) == 1 else "multi_document"
                ),
                reasoning_type="simple",
                use_citation="inline",
                llm=query_route_name(identity),
                origin="desktop",
                state=request_state,
            )
        if cancel_event is not None and cancel_event.is_set():
            return
        updates = (
            runtime.stream_turn(request, cancel_event=cancel_event)
            if cancel_event is not None
            else runtime.stream_turn(request)
        )
        for update in updates:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield _query_update(update, source_names)

    def recover_committed_turn(
        self,
        conversation_id: str,
        turn_id: str,
    ) -> dict[str, object] | None:
        with self._runtime_lock:
            return recover_committed_answer(
                self._get_runtime(),
                conversation_id,
                turn_id,
            )

    def validate_query(
        self,
        conversation_id: str,
        _prompt: str,
        selected_file_ids: list[str],
    ) -> dict[str, Any]:
        with self._runtime_lock:
            identity = self._ensure_model_routes()
            query_readiness = self._collect_query_readiness()
            if query_readiness is not None and not query_readiness.query_ready:
                raise DesktopQueryPreflightError.from_readiness(query_readiness)
            _selected_source_records(self._collect_files(), selected_file_ids)
            if self._get_runtime().load_session(conversation_id) is None:
                raise DesktopSessionNotFoundError(conversation_id)
            return query_route_diagnostics(identity, query_readiness)

    def rename_session(self, conversation_id: str, name: str) -> dict[str, Any]:
        with self._runtime_lock:
            runtime = self._get_runtime()
            try:
                runtime.rename_session(conversation_id, name)
            except PermissionError as exc:
                raise DesktopSessionNotFoundError(conversation_id) from exc
            session = runtime.load_session(conversation_id)
        if session is None:
            raise DesktopSessionNotFoundError(conversation_id)
        return _session_detail(session)

    def delete_session(self, conversation_id: str) -> str:
        with self._runtime_lock:
            try:
                self._get_runtime().delete_session(conversation_id)
            except PermissionError as exc:
                raise DesktopSessionNotFoundError(conversation_id) from exc
        return conversation_id

    def get_import_capabilities(self) -> dict[str, list[str]]:
        with self._runtime_lock:
            return self._collect_import_capabilities()

    def validate_indexing(self, paths: list[str]) -> None:
        with self._runtime_lock:
            self._ensure_model_routes()
            readiness = self._collect_indexing_readiness()
        if not readiness.indexing_ready:
            raise DesktopIndexingPreflightError.from_readiness(readiness)
        validate_index_sources(paths)

    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        with self._runtime_lock:
            self._ensure_model_routes()
            result = self._get_runtime().index_paths(paths, reindex=reindex).as_dict()
        return {
            "successes": [
                {"name": index_result_name(item)}
                for item in result.get("successes", [])
            ],
            "failures": [
                index_failure_from_result(item) for item in result.get("failures", [])
            ],
        }

    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        try:
            with self._runtime_lock:
                records = self._get_runtime().delete_files(file_ids)
        except ValueError as exc:
            raise DesktopFileNotFoundError(",".join(file_ids)) from exc
        except Exception as exc:
            raise DesktopMutationError(",".join(file_ids)) from exc
        return [
            {"file_id": str(record.file_id), "name": str(record.name)}
            for record in records
        ]

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        return self.delete_files([file_id])

    def _get_runtime(self) -> Any:
        self._ensure_model_routes()
        if self._runtime is None:
            self._runtime = self._create_runtime()
        return self._runtime

    def _ensure_model_routes(self) -> Any | None:
        if not self._routes_prepared:
            self._route_identity = self._prepare_model_routes()
            self._routes_prepared = True
        return self._route_identity


def _session_detail(session: Any) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    for user_message, assistant_message in session.messages:
        if str(user_message):
            messages.append({"role": "user", "content": str(user_message)})
        if str(assistant_message):
            messages.append({"role": "assistant", "content": str(assistant_message)})
    return {
        "conversation_id": str(session.conversation_id),
        "name": str(session.name or ""),
        "messages": messages,
        "graph_source_ids": [str(file_id) for file_id in session.graph_source_ids],
        "origin": str(session.origin or ""),
        "is_public": bool(session.is_public),
        "date_created": _serialize_datetime(session.date_created),
        "date_updated": _serialize_datetime(session.date_updated),
    }


def _selected_source_records(
    records: list[dict[str, Any]],
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {str(record.get("file_id") or ""): record for record in records}
    missing = [file_id for file_id in selected_file_ids if file_id not in by_id]
    if missing:
        raise DesktopFileNotFoundError(",".join(missing))
    return [by_id[file_id] for file_id in selected_file_ids]


def _source_identity_crosswalk(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "canonical_dataset_id": str(record["file_id"]),
            "runtime_file_id": str(record["file_id"]),
            "runtime_source_id": str(record["file_id"]),
            "filename": Path(str(record.get("name") or "")).name,
            "aliases": [Path(str(record.get("name") or "")).name],
        }
        for record in records
    ]


def _query_update(
    update: Any,
    source_names: dict[str, str],
) -> dict[str, Any]:
    response = getattr(update, "response", None)
    if response is not None:
        commit = response_terminal_commit(response)
        return {
            "stage": "completed",
            "answer": str(response.answer or ""),
            "final": True,
            "citations": _query_citations(response, source_names),
            "terminal_semantic_commit": commit,
            "terminal_outcome": str(commit.get("outcome") or ""),
            "terminal_outcome_reason": str(commit.get("outcome_reason") or ""),
        }
    event = getattr(update, "event", {})
    channel = str(event.get("channel") or "") if isinstance(event, dict) else ""
    stage = "generating" if channel == "chat" else "retrieving"
    return {
        "stage": stage,
        "answer": str(getattr(update, "answer", "") or ""),
        "final": False,
        "citations": [],
    }


def _query_citations(
    response: Any,
    source_names: dict[str, str],
) -> list[dict[str, str]]:
    bundle = (
        response.evidence_bundle if isinstance(response.evidence_bundle, dict) else {}
    )
    items = bundle.get("items")
    if not isinstance(items, list) or not items:
        metadata = (
            response.evidence_metadata
            if isinstance(response.evidence_metadata, dict)
            else {}
        )
        items = metadata.get("evidence", [])
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        file_ids = _citation_file_ids(item, source_names)
        for file_id in file_ids:
            citation_id = _citation_identifier(
                item,
                file_id,
            )
            identity = (file_id, citation_id)
            if identity in seen:
                continue
            seen.add(identity)
            citations.append(
                {
                    "citation_id": citation_id,
                    "file_id": file_id,
                    "file_name": source_names[file_id],
                    "page_label": _safe_locator(item.get("page_label")),
                    "element_id": _safe_locator(item.get("element_id")),
                    "quote": _citation_quote(item),
                }
            )
    return citations


def _citation_file_ids(
    item: dict[str, Any],
    source_names: dict[str, str],
) -> list[str]:
    raw_metadata = item.get("metadata")
    metadata: dict[str, Any] = (
        dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    )
    direct = _direct_citation_file_ids(item, metadata, source_names)
    if direct:
        return direct
    matched = _alias_citation_file_ids(item, metadata, source_names)
    if matched:
        return matched
    generic_reference = (
        str(item.get("source_id") or "").casefold() == "refs"
        or str(metadata.get("source") or "").casefold() == "references_html"
    )
    if generic_reference and len(source_names) == 1:
        return list(source_names)
    return []


def _direct_citation_file_ids(
    item: dict[str, Any],
    metadata: dict[str, Any],
    source_names: dict[str, str],
) -> list[str]:
    direct: list[str] = []
    for value in (
        item.get("runtime_source_id"),
        item.get("evaluation_source_id"),
        item.get("document_id"),
        item.get("source_id"),
        item.get("file_id"),
        metadata.get("file_id"),
        metadata.get("source_id"),
    ):
        candidate = str(value or "")
        if candidate in source_names and candidate not in direct:
            direct.append(candidate)
    for raw_backrefs in (
        item.get("source_backrefs"),
        metadata.get("source_backrefs"),
    ):
        if not isinstance(raw_backrefs, list):
            continue
        for value in raw_backrefs:
            candidate = str(value or "").split("#", 1)[0]
            if candidate in source_names and candidate not in direct:
                direct.append(candidate)
    return direct


def _alias_citation_file_ids(
    item: dict[str, Any],
    metadata: dict[str, Any],
    source_names: dict[str, str],
) -> list[str]:
    aliases: dict[str, set[str]] = {}
    for file_id, name in source_names.items():
        alias = Path(name).name.casefold()
        if alias:
            aliases.setdefault(alias, set()).add(file_id)
    matched: list[str] = []
    source_fields = (
        item.get("source_name"),
        item.get("file_name"),
        metadata.get("source_name"),
        metadata.get("file_name"),
    )
    for value in source_fields:
        alias = Path(str(value or "")).name.casefold()
        targets = aliases.get(alias, set())
        if len(targets) == 1:
            file_id = next(iter(targets))
            if file_id not in matched:
                matched.append(file_id)
    source_text = "\n".join(
        str(value or "").casefold()
        for value in (
            item.get("text"),
            item.get("caption"),
            item.get("ocr_text"),
            item.get("vlm_text"),
        )
    )
    for alias, targets in aliases.items():
        if (
            len(targets) == 1
            and _contains_exact_alias(source_text, alias)
            and (file_id := next(iter(targets))) not in matched
        ):
            matched.append(file_id)
    return matched


def _citation_identifier(
    item: dict[str, Any],
    file_id: str,
) -> str:
    import hashlib
    import json

    for key in ("evidence_id", "canonical_id", "runtime_identity"):
        candidate = _safe_locator(item.get(key), max_length=256)
        if candidate:
            digest = hashlib.sha256(
                f"{file_id}\0{candidate}".encode("utf-8")
            ).hexdigest()
            return f"citation-{digest[:24]}"
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{file_id}|{payload}".encode("utf-8")).hexdigest()
    return f"citation-{digest[:24]}"


def _contains_exact_alias(text: str, alias: str) -> bool:
    if not text or not alias:
        return False
    return (
        re.search(
            rf"(?<![\w.-]){re.escape(alias)}(?![\w.-])",
            text,
        )
        is not None
    )


def _safe_locator(value: Any, *, max_length: int = 128) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_length or any(char in text for char in "/\\\x00"):
        return ""
    return text


def _citation_quote(item: dict[str, Any]) -> str:
    for key in ("text", "caption", "ocr_text", "vlm_text"):
        value = str(item.get(key) or "").strip()
        if value:
            return value[:4_000]
    return ""


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
