from __future__ import annotations

import hashlib
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional, cast

from ktem.components import reasonings
from ktem.db.models import Conversation, Settings, User, engine
from ktem.embeddings.manager import embedding_models_manager
from ktem.index.file import FileIndex
from ktem.llms.manager import llms
from ktem.rerankings.manager import reranking_models_manager
from ktem.utils.commands import WEB_SEARCH_COMMAND
from ktem.utils.conversation import sync_retrieval_n_message
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings
from theflow.utils.modules import import_dotted_string

from . import _runtime_doctor as _doctor
from . import _runtime_elements, _runtime_graph
from . import _runtime_indexing as _indexing
from . import _runtime_mara as _mara
from . import _runtime_notebook as _nb
from . import _runtime_pipeline as _pipeline
from . import _runtime_selection as _selection
from . import _runtime_sessions as _sessions
from . import _runtime_turn as _turn
from . import debug_trace
from ._runtime_app import _DocQAPreviewService, _RuntimeAppContext
from ._runtime_models import (
    DocQADoctorResult,
    DocQAFileRecord,
    DocQAIndexResult,
    DocQARequest,
    DocQAResponse,
    DocQASession,
    DocQASessionSummary,
    DocQATurnUpdate,
    _PreparedPipeline,
)
from ._runtime_utils import _html_to_text, _serialize_value

logger = logging.getLogger(__name__)
DEFAULT_SETTING, STATE = "(default)", {"app": {"regen": False}}


def _log_stream_turn_text(event: str, session_info: Any, stream_result: Any) -> None:
    debug_trace.log_event(
        f"docqa_runtime.stream_turn.{event}",
        conversation_id=session_info.conversation_id,
        stream_text=debug_trace.summarize_text(stream_result.text),
        stream_event_count=len(stream_result.stream_events),
        include_stack=True,
    )


def _log_stream_turn_final_update(session_info: Any, response: Any) -> None:
    debug_trace.log_event(
        "docqa_runtime.stream_turn.final_update",
        conversation_id=session_info.conversation_id,
        response_answer=debug_trace.summarize_text(response.answer),
        response_messages=debug_trace.summarize_messages(response.messages),
        include_stack=True,
    )


def _build_turn_response(
    runtime: Any,
    *,
    session_info: DocQASession,
    prepared: _PreparedPipeline,
    stream_result: _turn.TurnStreamResult,
    messages: list,
    retrieval_history: list[str],
    plot_history: list[Any],
    selected_mapping: dict[str, Any],
    graph_source_ids: list[str],
) -> DocQAResponse:
    return DocQAResponse(
        conversation_id=session_info.conversation_id,
        answer=stream_result.text,
        references_html=stream_result.refs,
        references_text=_html_to_text(stream_result.refs),
        mindmap_html=stream_result.mindmap_html,
        plot=_serialize_value(stream_result.plot),
        messages=messages,
        retrieval_messages=retrieval_history,
        plot_history=_serialize_value(plot_history),
        state=_serialize_value(stream_result.state),
        selected_file_ids=prepared.selected_file_ids,
        selected_mapping=_serialize_value(selected_mapping),
        graph_source_ids=graph_source_ids,
        active_file_id=prepared.active_file_id,
        active_file_name=prepared.active_file_name,
        qa_scope=prepared.qa_scope,
        page_number=prepared.page_number,
        selected_text=prepared.selected_text,
        graph_context=_serialize_value(prepared.graph_context),
        reasoning_id=prepared.reasoning_id,
        settings=_serialize_value(prepared.settings),
        stream_events=stream_result.stream_events,
        graph_cache=_serialize_value(
            runtime.get_conversation_graph_cache(session_info.conversation_id)
        ),
        **_serialize_value(
            stream_result.capture.as_response_kwargs(stream_result.text)
        ),
    )


def _preview_value(preview: Any, method_name: str, file_id: str) -> str:
    method = getattr(preview, method_name, None)
    if method is None:
        return ""
    return str(method(file_id) or "")


def _graph_context_with_local_index(
    graph_context: dict[str, Any],
    file_index: Any,
    selected_file_ids: list[str],
) -> dict[str, Any]:
    if isinstance(graph_context.get("graph_index"), dict):
        return graph_context
    local_context = _runtime_graph.graph_context_for_selected_files(
        file_index,
        selected_file_ids,
    )
    if not local_context:
        return graph_context
    return {**graph_context, **local_context}


def _apply_multimodal_runtime_indexes(
    pipeline: Any,
    file_index: Any,
    selected_file_ids: list[str],
    active_file_id: str,
    graph_source_ids: list[str],
    graph_context: dict[str, Any],
) -> dict[str, Any]:
    file_ids = _selection.merge_unique_file_ids(selected_file_ids, [active_file_id])
    graph_file_ids = graph_source_ids or file_ids
    pipeline.element_index_records = (
        _runtime_elements.element_index_records_for_selected_files(
            file_index,
            file_ids,
        )
    )
    return _graph_context_with_local_index(graph_context, file_index, graph_file_ids)


def _apply_request_page_image_records(pipeline: Any, request: DocQARequest) -> None:
    if not request.page_image_records:
        return
    pipeline.page_image_index_records = [
        dict(item) for item in request.page_image_records if isinstance(item, dict)
    ]


def _artifact_source_scope(
    request: DocQARequest,
    prepared: _PreparedPipeline,
    graph_source_ids: list[str],
) -> dict[str, Any]:
    source_ids = _selection.merge_unique_file_ids(
        graph_source_ids,
        prepared.selected_file_ids,
        [prepared.active_file_id] if prepared.active_file_id else [],
    )
    scope: dict[str, Any] = {
        "mode": prepared.qa_scope or request.qa_scope or "document",
        "source_ids": source_ids,
    }
    if prepared.page_number is not None:
        scope["page"] = prepared.page_number
    note_ids = _selection.merge_unique_file_ids(request.note_ids or [])
    if note_ids:
        scope["note_ids"] = note_ids
    return scope


class DocQARuntime:
    def __init__(self, app=None, user_id: Any = None):
        self._app = app or _RuntimeAppContext()
        self._owns_app = app is None
        self._default_user_id = self._resolve_default_user_id()
        self._user_id = self._default_user_id if user_id is None else user_id
        self._preview = _DocQAPreviewService(self._app)
        self._web_search_cls = self._load_web_search_cls()
        self.file_index = self._get_default_file_index()
        self.knowledge_graph: Any = None
        if self.file_index is not None:
            from ktem.docqa.knowledge_graph import GlobalKnowledgeGraphService

            self.knowledge_graph = GlobalKnowledgeGraphService(
                self._app, self.file_index
            )

    @property
    def user_id(self):
        return self._user_id

    def _resolve_default_user_id(self):
        if not getattr(self._app, "f_user_management", False):
            return "default"
        return self._ensure_default_managed_user()

    def _ensure_default_managed_user(self) -> str:
        configured_username = str(
            getattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT_ADMIN", "admin")
            or "admin"
        ).strip()
        configured_password = str(
            getattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT_PASSWORD", "admin")
            or "admin"
        )
        username_lookup = configured_username.lower()

        try:
            with Session(engine) as session:
                existing = session.exec(
                    select(User).where(User.username_lower == username_lookup)
                ).first()
                if existing is not None:
                    return str(existing.id)

                fallback_admin = session.exec(
                    select(User).where(User.admin.is_(True))
                ).first()
                if fallback_admin is not None:
                    return str(fallback_admin.id)

                hashed_password = hashlib.sha256(
                    configured_password.encode()
                ).hexdigest()
                created = User(
                    username=configured_username,
                    username_lower=username_lookup,
                    password=hashed_password,
                    admin=True,
                )
                session.add(created)
                session.commit()
                session.refresh(created)
                return str(created.id)
        except Exception as exc:
            logger.warning("Failed to resolve managed default DocQA user: %s", exc)
            return ""

    @staticmethod
    def _normalize_selected_file_ids(selected_file_ids) -> list[str]:
        return _selection.normalize_selected_file_ids(selected_file_ids)

    @staticmethod
    def _normalize_page_number(page_number: Any) -> Optional[int]:
        return _selection.normalize_page_number(page_number)

    @staticmethod
    def _normalize_qa_scope(qa_scope: Any, page_number: Any = None) -> str:
        return _selection.normalize_qa_scope(qa_scope, page_number)

    @staticmethod
    def _merge_unique_file_ids(*groups) -> list[str]:
        return _selection.merge_unique_file_ids(*groups)

    @staticmethod
    def _extract_selected_ids_from_data_source(data_source: dict | None) -> list[str]:
        return _selection.extract_selected_ids_from_data_source(data_source)

    def _get_default_file_index(self) -> Optional[FileIndex]:
        for index in getattr(self._app.index_manager, "indices", []):
            if isinstance(index, FileIndex):
                return index
        return None

    def _resolve_user_id(self, user_id: Any = None):
        return self._user_id if user_id is None else user_id

    def _load_web_search_cls(self):
        backend = getattr(flowsettings, "KH_WEB_SEARCH_BACKEND", None)
        if not backend:
            return None
        try:
            return import_dotted_string(backend, safe=False)
        except Exception as exc:
            logger.warning("Failed to import web search backend %s: %s", backend, exc)
            return None

    def load_settings(self, user_id: Any = None) -> dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        settings = deepcopy(self._app.default_settings.flatten())
        with Session(engine) as session:
            statement = select(Settings).where(Settings.user == resolved_user_id)
            result = session.exec(statement).all()
            if result:
                settings.update(result[0].setting)
        return settings

    def list_sessions(self, user_id: Any = None) -> list[DocQASessionSummary]:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(engine) as session:
            statement = (
                select(Conversation)
                .where(
                    (Conversation.user == resolved_user_id)
                    | Conversation.is_public.is_(True)
                )
                .order_by(Conversation.date_created.desc())  # type: ignore[attr-defined]
            )
            rows = session.exec(statement).all()

        summaries = []
        for row in rows:
            data_source = dict(row.data_source or {})
            messages = data_source.get("messages", []) or []
            graph_source_ids = self._normalize_selected_file_ids(
                data_source.get("graph_source_ids", [])
            )
            summaries.append(
                DocQASessionSummary(
                    conversation_id=row.id,
                    name=row.name,
                    message_count=len(messages),
                    graph_source_count=len(graph_source_ids),
                    origin=str(data_source.get("origin", "") or ""),
                    is_public=bool(row.is_public),
                    date_created=row.date_created,
                    date_updated=row.date_updated,
                )
            )
        return summaries

    def load_session(self, conversation_id: str) -> Optional[DocQASession]:
        if not conversation_id:
            return None

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            row = session.exec(statement).one_or_none()

        if not row:
            return None

        data_source = dict(row.data_source or {})
        messages = [tuple(item) for item in (data_source.get("messages", []) or [])]
        retrieval_messages = list(data_source.get("retrieval_messages", []) or [])
        plot_history = list(data_source.get("plot_history", []) or [])
        state = deepcopy(data_source.get("state", STATE) or STATE)
        selected_mapping = dict(data_source.get("selected", {}) or {})
        graph_source_ids = self._normalize_selected_file_ids(
            data_source.get("graph_source_ids", [])
        )
        if not graph_source_ids:
            graph_source_ids = self._extract_selected_ids_from_data_source(data_source)

        return DocQASession(
            conversation_id=row.id,
            name=row.name,
            user_id=row.user,
            is_public=bool(row.is_public),
            data_source=data_source,
            messages=messages,
            retrieval_messages=sync_retrieval_n_message(
                [list(item) for item in messages], retrieval_messages
            ),
            plot_history=plot_history,
            state=state,
            selected_mapping=selected_mapping,
            graph_source_ids=graph_source_ids,
            origin=str(data_source.get("origin", "") or ""),
            date_created=row.date_created,
            date_updated=row.date_updated,
        )

    def create_session(
        self, name: str | None = None, user_id: Any = None
    ) -> DocQASession:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(engine) as session:
            row = Conversation(user=resolved_user_id)
            if name:
                row.name = name
            row.data_source = {"origin": "cli"}
            session.add(row)
            session.commit()
            session.refresh(row)
        session_info = self.load_session(row.id)
        assert session_info is not None
        return session_info

    def list_files(self, user_id: Any = None) -> list[DocQAFileRecord]:
        if not self.file_index:
            return []

        resolved_user_id = self._resolve_user_id(user_id)
        rows = self.file_index.list_source_rows(resolved_user_id)
        return [
            DocQAFileRecord(
                file_id=str(row.get("id", "") or ""),
                name=str(row.get("name", "") or ""),
                size=int(row.get("size", 0) or 0),
                tokens=int((row.get("note", {}) or {}).get("tokens", 0) or 0),
                loader=str((row.get("note", {}) or {}).get("loader", "") or ""),
                path=str(row.get("path", "") or ""),
                date_created=row.get("date_created"),
            )
            for row in rows
        ]

    def resolve_file_refs(
        self, refs: list[str], user_id: Any = None
    ) -> list[DocQAFileRecord]:
        records = self.list_files(user_id=user_id)
        return cast(list[DocQAFileRecord], _selection.resolve_file_refs(records, refs))

    def _selected_file_records_for_retrieval(
        self,
        selected_file_ids: list[str],
        active_file_id: str,
        user_id: Any,
    ) -> list[dict[str, Any]]:
        file_ids = self._merge_unique_file_ids(selected_file_ids, [active_file_id])
        if not file_ids:
            return []
        del user_id
        return [
            {
                "file_id": file_id,
                "file_name": _preview_value(
                    self._preview,
                    "resolve_file_name",
                    file_id,
                ),
                "path": _preview_value(self._preview, "resolve_file_path", file_id),
            }
            for file_id in file_ids
        ]

    def _build_selected_mapping(
        self,
        selected_inputs: dict[int, Any] | None,
        selected_file_ids: list[str],
        user_id: Any,
        existing_mapping: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        mapping = dict(existing_mapping or {})
        for index in getattr(self._app.index_manager, "indices", []):
            selected_input = None
            if isinstance(selected_inputs, dict):
                selected_input = selected_inputs.get(index.id)

            if index is self.file_index:
                if selected_input is None:
                    mode = "select" if selected_file_ids else "all"
                    selected_input = [mode, selected_file_ids, user_id]
                elif (
                    isinstance(selected_input, (list, tuple))
                    and len(selected_input) >= 3
                    and selected_input[0] in {"disabled", "select", "all"}
                ):
                    selected_input = list(selected_input[:3])
                else:
                    normalized_ids = self.file_index.resolve_selected_ids(
                        user_id, selected_input
                    )
                    mode = "select" if normalized_ids else "all"
                    selected_input = [mode, normalized_ids, user_id]
                mapping[str(index.id)] = selected_input
            elif selected_input is not None:
                mapping[str(index.id)] = selected_input
        return mapping

    def persist_conversation_state(
        self,
        conversation_id: str,
        user_id: Any,
        retrieval_message: str,
        plot_data: Any,
        retrieval_history: list[str],
        plot_history: list[Any],
        messages: list[tuple[str, str]],
        state: dict[str, Any],
        graph_source_ids: list[str],
        selected_inputs: Optional[dict[int, Any]] = None,
        selected_file_ids: Optional[list[str]] = None,
        origin: Optional[str] = None,
    ) -> tuple[list[str], list[Any]]:
        if not conversation_id:
            raise ValueError("No conversation selected")

        debug_trace.log_persist_state(
            "docqa_runtime.persist_conversation_state.start",
            conversation_id=conversation_id,
            user_id=user_id,
            messages=messages,
            retrieval_message=retrieval_message,
            graph_source_ids=graph_source_ids,
            selected_file_ids=selected_file_ids,
            origin=origin,
        )
        selected_file_ids = self._normalize_selected_file_ids(selected_file_ids)
        normalized_graph_ids = self._normalize_selected_file_ids(graph_source_ids)
        histories = _sessions.prepare_conversation_histories(
            retrieval_message=retrieval_message,
            plot_data=plot_data,
            retrieval_history=retrieval_history,
            plot_history=plot_history,
            state=state,
        )

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            row = session.exec(statement).one()

            data_source = dict(row.data_source or {})
            is_owner = row.user == user_id
            selected_mapping = self._build_selected_mapping(
                selected_inputs=selected_inputs,
                selected_file_ids=selected_file_ids,
                user_id=user_id,
                existing_mapping=data_source.get("selected", {}),
            )

            updated_data_source = _sessions.build_conversation_data_source(
                data_source=data_source,
                selected_mapping=selected_mapping,
                is_owner=is_owner,
                messages=messages,
                retrieval_history=histories.retrieval_history,
                plot_history=histories.plot_history,
                state=histories.state,
                graph_source_ids=normalized_graph_ids,
                origin=origin,
            )
            row.data_source = updated_data_source
            row.date_updated = datetime.now()
            session.add(row)
            session.commit()
            debug_trace.log_persist_state(
                "docqa_runtime.persist_conversation_state.committed",
                conversation_id=conversation_id,
                committed_messages=updated_data_source.get("messages", []),
                selected_mapping=selected_mapping,
                normalized_graph_ids=normalized_graph_ids,
            )

        return histories.retrieval_history, histories.plot_history

    def _resolve_selected_inputs(
        self, request: DocQARequest, session_info: Optional[DocQASession]
    ) -> dict[int, Any]:
        selected_inputs = dict(request.selected_inputs or {})
        if not self.file_index:
            return selected_inputs

        if request.selected_file_ids is not None:
            selected_inputs[self.file_index.id] = list(request.selected_file_ids)
            return selected_inputs

        if self.file_index.id in selected_inputs:
            return selected_inputs

        if session_info:
            selected_mapping = session_info.selected_mapping.get(
                str(self.file_index.id)
            )
            if selected_mapping is not None:
                selected_inputs[self.file_index.id] = selected_mapping
                return selected_inputs

            if session_info.graph_source_ids:
                selected_inputs[self.file_index.id] = list(
                    session_info.graph_source_ids
                )
                return selected_inputs

        return selected_inputs

    def _prepare_pipeline(self, request: DocQARequest) -> _PreparedPipeline:
        resolved_user_id = self._resolve_user_id(request.user_id)
        settings = deepcopy(request.settings or self.load_settings(resolved_user_id))
        state = deepcopy(request.state or STATE)
        selected_inputs = dict(request.selected_inputs or {})

        if request.reasoning_type in (DEFAULT_SETTING, None):
            reasoning_mode = settings["reasoning.use"]
        else:
            reasoning_mode = request.reasoning_type
        if reasoning_mode not in reasonings:
            raise ValueError(f"Unknown reasoning pipeline '{reasoning_mode}'.")

        reasoning_cls = reasonings[reasoning_mode]
        reasoning_id = reasoning_cls.get_info()["id"]

        _pipeline.apply_request_setting_overrides(settings, reasoning_id, request)

        retrievers = []
        if request.command_state == WEB_SEARCH_COMMAND:
            if not self._web_search_cls:
                raise ValueError("Web search back-end is not available.")
            retrievers.append(self._web_search_cls())
        else:
            for index in getattr(self._app.index_manager, "indices", []):
                selected_input = selected_inputs.get(index.id)
                retrievers.extend(
                    index.get_retriever_pipelines(
                        settings, resolved_user_id, selected_input
                    )
                )

        reasoning_state = _pipeline.build_reasoning_state(state, reasoning_id)
        pipeline = reasoning_cls.get_pipeline(settings, reasoning_state, retrievers)

        active_file_id = str(request.active_file_id or "")
        active_file_name = str(request.active_file_name or "")
        selected_file_ids: list[str] = []

        if self.file_index is not None:
            selected_input = selected_inputs.get(self.file_index.id)
            selected_file_ids = self.file_index.resolve_selected_ids(
                resolved_user_id, selected_input
            )

            if active_file_id and not active_file_name:
                active_file_name = self._preview.resolve_file_name(active_file_id)

            if not active_file_name:
                inferred_id, inferred_name, _ = self._preview.resolve_selected_file(
                    selected_file_ids
                )
                active_file_id = active_file_id or inferred_id
                active_file_name = active_file_name or inferred_name

        normalized_page_number = self._normalize_page_number(request.page_number)
        qa_scope = self._normalize_qa_scope(request.qa_scope, normalized_page_number)
        selected_text = str(request.selected_text or "").strip()
        if (
            qa_scope == "page"
            and (not selected_text)
            and normalized_page_number is not None
            and active_file_id
            and active_file_name
        ):
            selected_text = self._preview.get_page_context_text(
                active_file_id,
                active_file_name,
                normalized_page_number,
            )

        graph_context = (
            request.graph_context if isinstance(request.graph_context, dict) else {}
        )
        is_pdf_file = str(active_file_name or "").lower().endswith(".pdf")
        scoped_page_number = (
            normalized_page_number
            if qa_scope == "page" and is_pdf_file and normalized_page_number is not None
            else None
        )
        pipeline.active_file_id = active_file_id or ""
        pipeline.active_file_name = active_file_name
        pipeline.qa_scope = qa_scope
        pipeline.page_number = scoped_page_number
        pipeline.selected_text = selected_text
        pipeline.selected_file_records = self._selected_file_records_for_retrieval(
            selected_file_ids,
            active_file_id or "",
            resolved_user_id,
        )
        _apply_request_page_image_records(pipeline, request)
        graph_source_ids = self._normalize_selected_file_ids(request.graph_source_ids)
        graph_context = _apply_multimodal_runtime_indexes(
            pipeline,
            self.file_index,
            selected_file_ids,
            active_file_id,
            graph_source_ids,
            graph_context,
        )
        _mara.apply_request_context(pipeline, request, graph_context)

        return _PreparedPipeline(
            pipeline=pipeline,
            reasoning_state=reasoning_state,
            selected_file_ids=selected_file_ids,
            active_file_id=active_file_id or "",
            active_file_name=active_file_name,
            qa_scope=qa_scope,
            page_number=scoped_page_number,
            selected_text=selected_text,
            graph_context=graph_context,
            settings=settings,
            reasoning_id=reasoning_id,
        )

    def create_pipeline(self, request: DocQARequest):
        prepared = self._prepare_pipeline(request)
        return prepared.pipeline, prepared.reasoning_state

    def get_conversation_graph_cache(
        self, conversation_id: str
    ) -> Optional[dict[str, Any]]:
        if not conversation_id or not self.knowledge_graph:
            return None
        try:
            return self.knowledge_graph._load_cached_state(conversation_id)
        except Exception:
            return None

    def run_turn(self, request: DocQARequest) -> DocQAResponse:
        (
            resolved_user_id,
            session_info,
            selected_inputs,
            request_to_run,
            prepared,
            history,
        ) = self._prepare_turn_execution(request)
        stream_result = _turn.collect_stream_result(
            prepared,
            request_to_run,
            conversation_id=session_info.conversation_id,
            history=history,
            empty_message=self._empty_chat_message(),
        )
        return self._finalize_turn_response(
            original_request=request,
            request_to_run=request_to_run,
            resolved_user_id=resolved_user_id,
            session_info=session_info,
            selected_inputs=selected_inputs,
            prepared=prepared,
            history=history,
            stream_result=stream_result,
        )

    def stream_turn(self, request: DocQARequest) -> Iterator[DocQATurnUpdate]:
        debug_trace.log_runtime_stream_start(request)
        (
            resolved_user_id,
            session_info,
            selected_inputs,
            request_to_run,
            prepared,
            history,
        ) = self._prepare_turn_execution(request)
        stream_result = _turn.create_stream_result(request_to_run)

        for event in _turn.consume_stream_result(
            prepared,
            request_to_run,
            conversation_id=session_info.conversation_id,
            history=history,
            result=stream_result,
        ):
            partial_answer = _turn.partial_answer_text(stream_result.text)
            debug_trace.log_event(
                "docqa_runtime.stream_turn.event",
                conversation_id=session_info.conversation_id,
                stream_event=dict(event),
                raw_stream_text=debug_trace.summarize_text(stream_result.text),
                partial_answer=debug_trace.summarize_text(partial_answer),
                refs=debug_trace.summarize_html(stream_result.refs),
                stream_event_count=len(stream_result.stream_events),
            )
            yield DocQATurnUpdate(
                event=dict(event),
                answer=partial_answer,
                references_html=stream_result.refs,
                mindmap_html=stream_result.mindmap_html,
                plot=_serialize_value(stream_result.plot),
                state=_serialize_value(stream_result.state),
                stream_events=list(stream_result.stream_events),
            )

        _log_stream_turn_text(
            "before_finalize_stream_result", session_info, stream_result
        )
        _turn.finalize_stream_result(stream_result, self._empty_chat_message())
        _log_stream_turn_text(
            "after_finalize_stream_result", session_info, stream_result
        )
        response = self._finalize_turn_response(
            original_request=request,
            request_to_run=request_to_run,
            resolved_user_id=resolved_user_id,
            session_info=session_info,
            selected_inputs=selected_inputs,
            prepared=prepared,
            history=history,
            stream_result=stream_result,
        )
        _log_stream_turn_final_update(session_info, response)
        yield DocQATurnUpdate(
            answer=response.answer,
            references_html=response.references_html,
            mindmap_html=response.mindmap_html,
            plot=response.plot,
            state=response.state,
            stream_events=response.stream_events,
            response=response,
        )

    def _prepare_turn_execution(
        self,
        request: DocQARequest,
    ) -> tuple[
        Any, DocQASession, dict[int, Any], DocQARequest, _PreparedPipeline, list
    ]:
        resolved_user_id = self._resolve_user_id(request.user_id)
        session_info = (
            self.load_session(request.conversation_id)
            if request.conversation_id
            else None
        )
        if session_info is None:
            session_info = self.create_session(user_id=resolved_user_id)

        selected_inputs = self._resolve_selected_inputs(request, session_info)
        request_file_ids = _mara.selected_ids(self, resolved_user_id, selected_inputs)

        request_to_run = _turn.build_turn_request(
            request,
            session_info,
            resolved_user_id=resolved_user_id,
            selected_inputs=selected_inputs,
            request_file_ids=request_file_ids,
            load_settings=self.load_settings,
        )
        prepared = self._prepare_pipeline(request_to_run)
        history = list(request_to_run.history or [])
        return (
            resolved_user_id,
            session_info,
            selected_inputs,
            request_to_run,
            prepared,
            history,
        )

    def _finalize_turn_response(
        self,
        *,
        original_request: DocQARequest,
        request_to_run: DocQARequest,
        resolved_user_id: Any,
        session_info: DocQASession,
        selected_inputs: dict[int, Any],
        prepared: _PreparedPipeline,
        history: list,
        stream_result: _turn.TurnStreamResult,
    ) -> DocQAResponse:
        messages = history + [(original_request.prompt, stream_result.text)]
        debug_trace.log_runtime_finalize_response(
            "docqa_runtime.finalize_turn_response.start",
            conversation_id=session_info.conversation_id,
            stream_text=stream_result.text,
            messages=messages,
            refs=stream_result.refs,
        )
        existing_graph_source_ids = list(session_info.graph_source_ids or [])
        graph_source_ids = _turn.graph_source_ids_for_turn(
            original_request.graph_source_ids,
            prepared.selected_file_ids,
            existing_graph_source_ids,
            self._normalize_selected_file_ids,
        )

        retrieval_history, plot_history = self.persist_conversation_state(
            conversation_id=session_info.conversation_id,
            user_id=resolved_user_id,
            retrieval_message=stream_result.refs,
            plot_data=stream_result.plot,
            retrieval_history=session_info.retrieval_messages,
            plot_history=session_info.plot_history,
            messages=messages,
            state=stream_result.state,
            graph_source_ids=graph_source_ids,
            selected_inputs=selected_inputs,
            selected_file_ids=prepared.selected_file_ids,
            origin=original_request.origin,
        )
        self._save_turn_artifact(
            session_info.conversation_id,
            request_to_run,
            prepared,
            graph_source_ids,
            stream_result,
        )

        selected_mapping = self._build_selected_mapping(
            selected_inputs=selected_inputs,
            selected_file_ids=prepared.selected_file_ids,
            user_id=resolved_user_id,
            existing_mapping=session_info.selected_mapping,
        )

        response = _build_turn_response(
            self,
            session_info=session_info,
            prepared=prepared,
            stream_result=stream_result,
            messages=messages,
            retrieval_history=retrieval_history,
            plot_history=plot_history,
            selected_mapping=selected_mapping,
            graph_source_ids=graph_source_ids,
        )
        debug_trace.log_runtime_finalize_response(
            "docqa_runtime.finalize_turn_response.return",
            conversation_id=session_info.conversation_id,
            response=response,
        )
        return response

    @staticmethod
    def _save_turn_artifact(
        conversation_id: str,
        request: DocQARequest,
        prepared: _PreparedPipeline,
        graph_source_ids: list[str],
        stream_result: _turn.TurnStreamResult,
    ) -> None:
        _nb.save_captured_artifact(
            conversation_id,
            stream_result.capture.artifact,
            artifact_type=request.artifact_type or request.task_type,
            prompt=request.prompt,
            source_scope=_artifact_source_scope(request, prepared, graph_source_ids),
        )

    @staticmethod
    def _empty_chat_message() -> str:
        return getattr(
            flowsettings,
            "KH_CHAT_EMPTY_MSG_PLACEHOLDER",
            "(Sorry, I don't know)",
        )

    def _expand_zip_inputs(self, paths: list[str]) -> list[str]:
        return _indexing.expand_zip_inputs(
            self.file_index,
            paths,
            zip_input_dir=flowsettings.KH_ZIP_INPUT_DIR,
        )

    def _expand_index_inputs(self, paths: list[str]) -> list[str]:
        return _indexing.expand_index_inputs(
            self.file_index,
            paths,
            zip_input_dir=flowsettings.KH_ZIP_INPUT_DIR,
        )

    def index_paths(
        self,
        paths: list[str],
        reindex: bool = False,
        user_id: Any = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> DocQAIndexResult:
        return _indexing.index_paths(
            self.file_index,
            paths,
            reindex=reindex,
            settings=settings,
            load_settings=self.load_settings,
            resolve_user_id=self._resolve_user_id,
            user_id=user_id,
            zip_input_dir=flowsettings.KH_ZIP_INPUT_DIR,
        )

    def delete_files(
        self, refs: list[str], user_id: Any = None
    ) -> list[DocQAFileRecord]:
        if not self.file_index:
            return []

        resolved_user_id = self._resolve_user_id(user_id)
        matches = self.resolve_file_refs(refs, user_id=resolved_user_id)
        source_table = cast(Any, self.file_index._resources["Source"])
        index_table = cast(Any, self.file_index._resources["Index"])
        vector_store = cast(Any, self.file_index._resources["VectorStore"])
        doc_store = cast(Any, self.file_index._resources["DocStore"])
        file_storage_path = cast(Any, self.file_index._resources.get("FileStoragePath"))

        for match in matches:
            stored_rel_path = ""
            vector_ids: list[str] = []
            document_ids: list[str] = []

            with Session(engine) as session:
                source_row = session.exec(
                    select(source_table).where(source_table.id == match.file_id)
                ).one_or_none()
                if source_row is None:
                    continue

                stored_rel_path = str(getattr(source_row, "path", "") or "")
                session.delete(source_row)

                index_rows = session.exec(
                    select(index_table).where(index_table.source_id == match.file_id)
                ).all()
                for row in index_rows:
                    relation_type = str(getattr(row, "relation_type", "") or "")
                    target_id = str(getattr(row, "target_id", "") or "")
                    if relation_type == "vector" and target_id:
                        vector_ids.append(target_id)
                    elif relation_type == "document" and target_id:
                        document_ids.append(target_id)
                    session.delete(row)

                session.commit()

            if vector_ids and vector_store:
                vector_store.delete(vector_ids)
            if document_ids:
                doc_store.delete(document_ids)

            if stored_rel_path:
                candidate_paths = []
                if file_storage_path:
                    candidate_paths.append(Path(file_storage_path) / stored_rel_path)
                candidate_paths.append(Path(stored_rel_path))
                for candidate in candidate_paths:
                    try:
                        if candidate.is_file():
                            candidate.unlink()
                            break
                    except Exception:
                        continue
        return matches

    def doctor(self, user_id: Any = None) -> DocQADoctorResult:
        resolved_user_id = self._resolve_user_id(user_id)
        return _doctor.build_doctor_result(
            app=self._app,
            file_index=self.file_index,
            knowledge_graph=self.knowledge_graph,
            resolved_user_id=resolved_user_id,
            list_files=self.list_files,
            list_sessions=self.list_sessions,
            llms_manager=llms,
            embedding_manager=embedding_models_manager,
            reranking_manager=reranking_models_manager,
        )
