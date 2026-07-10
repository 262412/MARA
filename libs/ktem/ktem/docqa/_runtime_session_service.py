from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Optional

from ktem.db.models import Conversation, Settings
from ktem.utils.conversation import sync_retrieval_n_message
from sqlmodel import Session, select

from . import _runtime_selection as _selection
from . import _runtime_sessions as _sessions
from ._runtime_models import DocQASession, DocQASessionSummary


class RuntimeSessionService:
    def __init__(
        self,
        *,
        app: Any,
        file_index: Any,
        engine: Any,
        resolve_user_id: Callable[[Any], Any],
    ) -> None:
        self._app = app
        self._file_index = file_index
        self._engine = engine
        self._resolve_user_id = resolve_user_id

    def load_settings(self, user_id: Any = None) -> dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        settings = deepcopy(self._app.default_settings.flatten())
        with Session(self._engine) as session:
            statement = select(Settings).where(Settings.user == resolved_user_id)
            result = session.exec(statement).all()
            if result:
                settings.update(result[0].setting)
        return settings

    def list_sessions(
        self,
        user_id: Any = None,
        *,
        include_public: bool = True,
        public_first: bool = False,
    ) -> list[DocQASessionSummary]:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            statement = select(Conversation)
            if include_public:
                statement = statement.where(
                    (Conversation.user == resolved_user_id)
                    | Conversation.is_public.is_(True)
                )
            else:
                statement = statement.where(Conversation.user == resolved_user_id)
            if public_first:
                statement = statement.order_by(
                    Conversation.is_public.desc(),
                    Conversation.date_created.desc(),  # type: ignore[attr-defined]
                )
            else:
                statement = statement.order_by(
                    Conversation.date_created.desc()  # type: ignore[attr-defined]
                )
            rows = session.exec(statement).all()

        return [self._session_summary(row) for row in rows]

    @staticmethod
    def _session_summary(row: Conversation) -> DocQASessionSummary:
        data_source = dict(row.data_source or {})
        messages = data_source.get("messages", []) or []
        graph_source_ids = _selection.normalize_selected_file_ids(
            data_source.get("graph_source_ids", [])
        )
        return DocQASessionSummary(
            conversation_id=row.id,
            name=row.name,
            message_count=len(messages),
            graph_source_count=len(graph_source_ids),
            origin=str(data_source.get("origin", "") or ""),
            is_public=bool(row.is_public),
            date_created=row.date_created,
            date_updated=row.date_updated,
        )

    def load_session(
        self,
        conversation_id: str,
        *,
        user_id: Any = None,
    ) -> Optional[DocQASession]:
        if not conversation_id:
            return None

        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            statement = select(Conversation).where(
                Conversation.id == conversation_id,
                (Conversation.user == resolved_user_id)
                | Conversation.is_public.is_(True),
            )
            row = session.exec(statement).one_or_none()

        if row is None:
            return None
        return self._loaded_session(row)

    @staticmethod
    def _loaded_session(row: Conversation) -> DocQASession:
        data_source = dict(row.data_source or {})
        messages = [tuple(item) for item in (data_source.get("messages", []) or [])]
        retrieval_messages = list(data_source.get("retrieval_messages", []) or [])
        plot_history = list(data_source.get("plot_history", []) or [])
        state = deepcopy(data_source.get("state", _sessions.STATE) or _sessions.STATE)
        selected_mapping = dict(data_source.get("selected", {}) or {})
        graph_source_ids = _selection.normalize_selected_file_ids(
            data_source.get("graph_source_ids", [])
        )
        if not graph_source_ids:
            graph_source_ids = _selection.extract_selected_ids_from_data_source(
                data_source
            )

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
        self,
        name: str | None = None,
        user_id: Any = None,
    ) -> DocQASession:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = Conversation(user=resolved_user_id)
            if name:
                row.name = name
            row.data_source = {"origin": "cli"}
            session.add(row)
            session.commit()
            session.refresh(row)
        session_info = self.load_session(row.id, user_id=resolved_user_id)
        assert session_info is not None
        return session_info

    def build_selected_mapping(
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

            if index is self._file_index:
                selected_input = self._file_index_selection(
                    selected_input,
                    selected_file_ids,
                    user_id,
                )
                mapping[str(index.id)] = selected_input
            elif selected_input is not None:
                mapping[str(index.id)] = selected_input
        return mapping

    def _file_index_selection(
        self,
        selected_input: Any,
        selected_file_ids: list[str],
        user_id: Any,
    ) -> list[Any]:
        if selected_input is None:
            mode = "select" if selected_file_ids else "all"
            return [mode, selected_file_ids, user_id]
        if (
            isinstance(selected_input, (list, tuple))
            and len(selected_input) >= 3
            and selected_input[0] in {"disabled", "select", "all"}
        ):
            return list(selected_input[:3])
        normalized_ids = self._file_index.resolve_selected_ids(
            user_id,
            selected_input,
        )
        mode = "select" if normalized_ids else "all"
        return [mode, normalized_ids, user_id]

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

        resolved_user_id = self._resolve_user_id(user_id)
        normalized_file_ids = _selection.normalize_selected_file_ids(selected_file_ids)
        normalized_graph_ids = _selection.normalize_selected_file_ids(graph_source_ids)
        histories = _sessions.prepare_conversation_histories(
            retrieval_message=retrieval_message,
            plot_data=plot_data,
            retrieval_history=retrieval_history,
            plot_history=plot_history,
            state=state,
        )

        with Session(self._engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            row = session.exec(statement).one()
            if row.user != resolved_user_id and not row.is_public:
                raise PermissionError(
                    "Conversation is outside the authenticated user scope: "
                    f"conversation_id={conversation_id}"
                )

            data_source = dict(row.data_source or {})
            is_owner = row.user == resolved_user_id
            selected_mapping = self.build_selected_mapping(
                selected_inputs=selected_inputs,
                selected_file_ids=normalized_file_ids,
                user_id=resolved_user_id,
                existing_mapping=data_source.get("selected", {}),
            )
            row.data_source = _sessions.build_conversation_data_source(
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
            row.date_updated = datetime.now()
            session.add(row)
            session.commit()

        return histories.retrieval_history, histories.plot_history


__all__ = ["RuntimeSessionService"]
