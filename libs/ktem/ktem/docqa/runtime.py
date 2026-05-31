from __future__ import annotations

import hashlib
import logging
import tempfile
import zipfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

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

from kotaemon.base import Document

from . import _runtime_mara as _mara
from . import _runtime_notebook as _nb
from ._runtime_app import _DocQAPreviewService, _RuntimeAppContext
from ._runtime_models import (
    DocQADoctorResult,
    DocQAFileRecord,
    DocQAIndexResult,
    DocQARequest,
    DocQAResponse,
    DocQASession,
    DocQASessionSummary,
    _PreparedPipeline,
)
from ._runtime_utils import _html_to_text, _serialize_value

logger = logging.getLogger(__name__)
DEFAULT_SETTING, STATE = "(default)", {"app": {"regen": False}}


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
        if selected_file_ids in (None, ""):
            return []
        if isinstance(selected_file_ids, list):
            return [str(item) for item in selected_file_ids if item not in (None, "")]
        return [str(selected_file_ids)]

    @staticmethod
    def _normalize_page_number(page_number: Any) -> Optional[int]:
        if page_number in (None, ""):
            return None
        return max(1, int(page_number))

    @staticmethod
    def _normalize_qa_scope(qa_scope: Any, page_number: Any = None) -> str:
        value = str(qa_scope or "auto").strip().lower().replace("-", "_")
        if value in {"", "auto"}:
            return "page" if page_number not in (None, "") else "document"
        if value in {"doc", "whole_document", "full_document"}:
            return "document"
        if value in {"multi", "multi_doc", "multi_docs", "multi_document"}:
            return "multi_document"
        if value not in {"page", "document", "multi_document"}:
            raise ValueError(
                "Unknown QA scope '{}'. Expected page, document, multi-document, "
                "or auto.".format(qa_scope)
            )
        return value

    @staticmethod
    def _merge_unique_file_ids(*groups) -> list[str]:
        merged: list[str] = []
        seen = set()
        for group in groups:
            if group in (None, ""):
                continue
            values = group if isinstance(group, list) else [group]
            for value in values:
                item = str(value or "").strip()
                if not item or item in seen:
                    continue
                seen.add(item)
                merged.append(item)
        return merged

    @staticmethod
    def _extract_selected_ids_from_data_source(data_source: dict | None) -> list[str]:
        if not isinstance(data_source, dict):
            return []

        selected = data_source.get("selected", {})
        if not isinstance(selected, dict):
            return []

        file_ids: list[str] = []
        for value in selected.values():
            if (
                isinstance(value, list)
                and len(value) >= 3
                and str(value[0] or "").strip() in {"disabled", "select", "all"}
            ):
                candidates = [value[1]]
            else:
                candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if isinstance(candidate, list):
                    for nested in candidate:
                        if isinstance(nested, (dict, tuple, list)):
                            continue
                        item = str(nested or "").strip()
                        if not item or item.lower() in {"select", "upload", "all"}:
                            continue
                        file_ids.append(item)
                else:
                    if isinstance(candidate, (dict, tuple)):
                        continue
                    item = str(candidate or "").strip()
                    if not item or item.lower() in {"select", "upload", "all"}:
                        continue
                    file_ids.append(item)
        return DocQARuntime._merge_unique_file_ids(file_ids)

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
                .order_by(
                    Conversation.date_created.desc()
                )  # type: ignore[attr-defined]
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
        if not refs:
            return records

        by_id = {record.file_id: record for record in records}
        by_name: dict[str, list[DocQAFileRecord]] = {}
        for record in records:
            by_name.setdefault(record.name.lower(), []).append(record)

        resolved: list[DocQAFileRecord] = []
        seen: set[str] = set()
        for ref in refs:
            key = str(ref or "").strip()
            if not key:
                continue

            match: Optional[DocQAFileRecord] = by_id.get(key)
            if match is None:
                exact = by_name.get(key.lower(), [])
                if len(exact) == 1:
                    match = exact[0]
                elif len(exact) > 1:
                    raise ValueError(f"File reference '{key}' is ambiguous.")

            if match is None:
                contains = [
                    record
                    for record in records
                    if key.lower() in record.name.lower()
                    or key.lower() in record.file_id.lower()
                ]
                if len(contains) == 1:
                    match = contains[0]
                elif len(contains) > 1:
                    raise ValueError(f"File reference '{key}' is ambiguous.")

            if match is None:
                raise ValueError(f"Unable to resolve file reference '{key}'.")

            if match.file_id not in seen:
                seen.add(match.file_id)
                resolved.append(match)

        return resolved

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

        selected_file_ids = self._normalize_selected_file_ids(selected_file_ids)
        normalized_graph_ids = self._normalize_selected_file_ids(graph_source_ids)

        state_to_store = deepcopy(state or STATE)
        retrieval_history_to_store = list(retrieval_history or [])
        plot_history_to_store = list(plot_history or [])

        if not state_to_store.get("app", {}).get("regen", False):
            retrieval_history_to_store = retrieval_history_to_store + [
                retrieval_message
            ]
            plot_history_to_store = plot_history_to_store + [plot_data]
        else:
            if retrieval_history_to_store:
                retrieval_history_to_store[-1] = retrieval_message
            if plot_history_to_store:
                plot_history_to_store[-1] = plot_data
        state_to_store.setdefault("app", {})["regen"] = False

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

            updated_data_source = {
                "selected": (
                    selected_mapping if is_owner else data_source.get("selected", {})
                ),
                "messages": messages,
                "retrieval_messages": retrieval_history_to_store,
                "plot_history": plot_history_to_store,
                "state": state_to_store,
                "graph_source_ids": normalized_graph_ids,
                "likes": deepcopy(data_source.get("likes", [])),
            }
            if "chat_suggestions" in data_source:
                updated_data_source["chat_suggestions"] = deepcopy(
                    data_source.get("chat_suggestions", [])
                )
            if origin or data_source.get("origin"):
                updated_data_source["origin"] = origin or data_source.get("origin")
            updated_data_source = _nb.preserve_state(updated_data_source, data_source)
            row.data_source = updated_data_source
            row.date_updated = datetime.now()
            session.add(row)
            session.commit()

        return retrieval_history_to_store, plot_history_to_store

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

        llm_setting_key = f"reasoning.options.{reasoning_id}.llm"
        if llm_setting_key in settings and request.llm not in (
            DEFAULT_SETTING,
            None,
            "",
        ):
            settings[llm_setting_key] = request.llm
        if request.use_mindmap not in (DEFAULT_SETTING, None):
            settings["reasoning.options.simple.create_mindmap"] = request.use_mindmap
        if request.use_citation not in (DEFAULT_SETTING, None):
            settings[
                "reasoning.options.simple.highlight_citation"
            ] = request.use_citation
        if request.language not in (DEFAULT_SETTING, None, ""):
            settings["reasoning.lang"] = request.language

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

        reasoning_state = {
            "app": deepcopy((state or {}).get("app", STATE["app"])),
            "pipeline": deepcopy((state or {}).get(reasoning_id, {})),
        }
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

        request_to_run = DocQARequest(
            prompt=request.prompt,
            conversation_id=session_info.conversation_id,
            selected_file_ids=request_file_ids,
            selected_inputs=selected_inputs,
            active_file_id=request.active_file_id,
            active_file_name=request.active_file_name,
            qa_scope=request.qa_scope,
            page_number=request.page_number,
            selected_text=request.selected_text,
            graph_context=deepcopy(request.graph_context),
            graph_source_ids=deepcopy(request.graph_source_ids),
            settings=deepcopy(request.settings or self.load_settings(resolved_user_id)),
            state=deepcopy(request.state or session_info.state),
            history=list(request.history or session_info.messages),
            reasoning_type=request.reasoning_type,
            llm=request.llm,
            use_mindmap=request.use_mindmap,
            use_citation=request.use_citation,
            language=request.language,
            command_state=request.command_state,
            user_id=resolved_user_id,
            origin=request.origin,
        )
        _mara.copy_request_fields(request_to_run, request)
        prepared = self._prepare_pipeline(request_to_run)
        request_state = request_to_run.state or deepcopy(STATE)
        request_to_run.state = request_state

        history = list(request_to_run.history or [])
        text = ""
        refs = ""
        plot = None
        mindmap_html = ""
        stream_events: list[dict[str, Any]] = []
        mara_capture = _mara.ResponseCapture()

        for response in prepared.pipeline.stream(
            request.prompt,
            session_info.conversation_id,
            history,
        ):
            if not isinstance(response, Document) or response.channel is None:
                continue

            event = {
                "channel": response.channel,
                "content": _serialize_value(response.content),
            }
            stream_events.append(event)
            mara_capture.ingest(response.channel, event["content"])

            if response.channel == "chat":
                if response.content is None:
                    text = ""
                else:
                    text += str(response.content)
            elif response.channel == "info":
                if response.content is None:
                    refs = ""
                    mindmap_html = ""
                else:
                    refs += str(response.content)
                if "markmap" in str(response.content):
                    mindmap_html += str(response.content)
            elif response.channel == "plot":
                plot = response.content

            pipeline_id = str(prepared.pipeline.get_info()["id"])
            request_state.setdefault(pipeline_id, {})
            request_state[pipeline_id] = prepared.reasoning_state["pipeline"]

        if not text:
            text = getattr(
                flowsettings,
                "KH_CHAT_EMPTY_MSG_PLACEHOLDER",
                "(Sorry, I don't know)",
            )

        messages = history + [(request.prompt, text)]
        existing_graph_source_ids = list(session_info.graph_source_ids or [])
        graph_source_ids = self._normalize_selected_file_ids(request.graph_source_ids)
        if not graph_source_ids:
            graph_source_ids = (
                list(prepared.selected_file_ids)
                if prepared.selected_file_ids
                else existing_graph_source_ids
            )

        retrieval_history, plot_history = self.persist_conversation_state(
            conversation_id=session_info.conversation_id,
            user_id=resolved_user_id,
            retrieval_message=refs,
            plot_data=plot,
            retrieval_history=session_info.retrieval_messages,
            plot_history=session_info.plot_history,
            messages=messages,
            state=request_state,
            graph_source_ids=graph_source_ids,
            selected_inputs=selected_inputs,
            selected_file_ids=prepared.selected_file_ids,
            origin=request.origin,
        )
        _nb.save_captured_artifact(session_info.conversation_id, mara_capture.artifact)

        selected_mapping = self._build_selected_mapping(
            selected_inputs=selected_inputs,
            selected_file_ids=prepared.selected_file_ids,
            user_id=resolved_user_id,
            existing_mapping=session_info.selected_mapping,
        )

        return DocQAResponse(
            conversation_id=session_info.conversation_id,
            answer=text,
            references_html=refs,
            references_text=_html_to_text(refs),
            mindmap_html=mindmap_html,
            plot=_serialize_value(plot),
            messages=messages,
            retrieval_messages=retrieval_history,
            plot_history=_serialize_value(plot_history),
            state=_serialize_value(request_state),
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
            stream_events=stream_events,
            graph_cache=_serialize_value(
                self.get_conversation_graph_cache(session_info.conversation_id)
            ),
            **_serialize_value(mara_capture.as_response_kwargs()),
        )

    def _expand_zip_inputs(self, paths: list[str]) -> list[str]:
        if not self.file_index:
            return paths

        supported_types = {
            item.strip().lower()
            for item in str(
                self.file_index.config.get("supported_file_types", "")
            ).split(",")
            if item.strip()
        }
        expanded: list[str] = []
        for raw_path in paths:
            if raw_path.startswith("http://") or raw_path.startswith("https://"):
                expanded.append(raw_path)
                continue

            path = Path(raw_path)
            if path.suffix.lower() != ".zip":
                expanded.append(str(path))
                continue

            out_dir = Path(
                tempfile.mkdtemp(
                    dir=str(flowsettings.KH_ZIP_INPUT_DIR),
                    prefix=f"{path.stem}_",
                )
            )
            with zipfile.ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(out_dir)

            for child in sorted(out_dir.rglob("*")):
                if not child.is_file():
                    continue
                if (
                    child.suffix.lower() in supported_types
                    and child.suffix.lower() != ".zip"
                ):
                    expanded.append(str(child.resolve()))
        return expanded

    def _expand_index_inputs(self, paths: list[str]) -> list[str]:
        if not self.file_index:
            return []

        supported_types = {
            item.strip().lower()
            for item in str(
                self.file_index.config.get("supported_file_types", "")
            ).split(",")
            if item.strip()
        }
        collected: list[str] = []
        for raw_path in paths:
            candidate = str(raw_path or "").strip()
            if not candidate:
                continue

            if candidate.startswith("http://") or candidate.startswith("https://"):
                collected.append(candidate)
                continue

            path = Path(candidate).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"Path does not exist: {candidate}")

            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and child.suffix.lower() in supported_types:
                        collected.append(str(child.resolve()))
                continue

            collected.append(str(path.resolve()))

        return self._expand_zip_inputs(collected)

    def index_paths(
        self,
        paths: list[str],
        reindex: bool = False,
        user_id: Any = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> DocQAIndexResult:
        if not self.file_index:
            raise ValueError("No file index is configured.")

        resolved_user_id = self._resolve_user_id(user_id)
        runtime_settings = deepcopy(settings or self.load_settings(resolved_user_id))
        expanded_paths = self._expand_index_inputs(paths)
        pipeline = self.file_index.get_indexing_pipeline(
            runtime_settings, resolved_user_id
        )

        successes: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        debug_messages: list[str] = []
        index_inputs = cast(list[str | Path], expanded_paths)
        for response in pipeline.stream(index_inputs, reindex=reindex):
            if response.channel == "debug":
                debug_messages.append(str(response.text))
            elif response.channel == "index":
                content = dict(response.content or {})
                serialized = {
                    key: _serialize_value(value) for key, value in content.items()
                }
                if serialized.get("status") == "success":
                    successes.append(serialized)
                else:
                    failures.append(serialized)

        return DocQAIndexResult(
            successes=successes,
            failures=failures,
            debug_messages=debug_messages,
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
        issues: list[str] = []
        warnings: list[str] = []

        index_name = ""
        index_id: int | None = None
        if self.file_index is None:
            issues.append("No default FileIndex is available.")
        else:
            index_name = self.file_index.name
            index_id = self.file_index.id

        try:
            default_llm = llms.get_default_name()
        except Exception as exc:
            default_llm = ""
            if isinstance(exc, ValueError) and "No models in pool" in str(exc):
                warnings.append(
                    "No default LLM configured yet. "
                    "DocQA doctor can still run before model setup."
                )
            else:
                issues.append(f"Unable to load default LLM: {exc}")

        try:
            default_embedding = embedding_models_manager.get_default_name()
        except Exception as exc:
            default_embedding = ""
            if isinstance(exc, ValueError) and "No models in pool" in str(exc):
                warnings.append(
                    "No default embedding model configured yet. "
                    "DocQA doctor can still run before model setup."
                )
            else:
                issues.append(f"Unable to load default embedding model: {exc}")

        warnings.extend(
            f"Invalid LLM configuration: {error}" for error in llms.load_errors()
        )
        warnings.extend(
            f"Invalid embedding configuration: {error}"
            for error in embedding_models_manager.load_errors()
        )
        warnings.extend(
            f"Invalid reranking configuration: {error}"
            for error in reranking_models_manager.load_errors()
        )

        try:
            file_count = len(self.list_files(user_id=resolved_user_id))
        except Exception as exc:
            file_count = 0
            issues.append(f"Unable to read indexed files: {exc}")

        try:
            session_count = len(self.list_sessions(user_id=resolved_user_id))
        except Exception as exc:
            session_count = 0
            issues.append(f"Unable to read saved sessions: {exc}")

        graph_cache_dir = ""
        if self.knowledge_graph is not None:
            graph_cache_dir = str(self.knowledge_graph._storage_dir)

        return DocQADoctorResult(
            ok=not issues,
            app_name=getattr(self._app, "app_name", "MARA"),
            default_user_id=resolved_user_id,
            index_name=index_name,
            index_id=index_id,
            llm_default=default_llm,
            embedding_default=default_embedding,
            file_count=file_count,
            session_count=session_count,
            graph_cache_dir=graph_cache_dir,
            issues=issues,
            warnings=warnings,
        )
