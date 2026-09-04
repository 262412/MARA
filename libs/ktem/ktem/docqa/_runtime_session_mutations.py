from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from ktem.db.models import Conversation
from sqlmodel import Session, select

from . import _runtime_selection as _selection


class RuntimeSessionMutationService:
    def __init__(
        self,
        *,
        engine: Any,
        resolve_user_id: Callable[[Any], Any],
    ) -> None:
        self._engine = engine
        self._resolve_user_id = resolve_user_id

    def delete_session(self, conversation_id: str, user_id: Any = None) -> None:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            session.delete(row)
            session.commit()

    def rename_session(
        self,
        conversation_id: str,
        name: str,
        user_id: Any = None,
    ) -> None:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            row.name = name
            session.add(row)
            session.commit()

    def update_chat_suggestions(
        self,
        conversation_id: str,
        suggestions: list[str],
        user_id: Any = None,
    ) -> None:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            data_source = deepcopy(row.data_source or {})
            data_source["chat_suggestions"] = [[item] for item in suggestions]
            row.data_source = data_source
            session.add(row)
            session.commit()

    def set_session_public(
        self,
        conversation_id: str,
        is_public: bool,
        user_id: Any = None,
    ) -> str:
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            if row.is_public != bool(is_public):
                row.is_public = bool(is_public)
                session.add(row)
                session.commit()
            return row.name

    def persist_graph_source_ids(
        self,
        conversation_id: str,
        source_ids: list[str],
        user_id: Any = None,
    ) -> list[str]:
        resolved_user_id = self._resolve_user_id(user_id)
        normalized_ids = _selection.merge_unique_file_ids(source_ids)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            data_source = deepcopy(row.data_source or {})
            if data_source.get("graph_source_ids") != normalized_ids:
                data_source["graph_source_ids"] = normalized_ids
                row.data_source = data_source
                session.add(row)
                session.commit()
        return normalized_ids

    def append_session_like(
        self,
        conversation_id: str,
        index: Any,
        value: Any,
        liked: bool,
        user_id: Any = None,
    ) -> None:
        """Record feedback only when the authenticated user owns the session."""
        resolved_user_id = self._resolve_user_id(user_id)
        with Session(self._engine) as session:
            row = self._owner_row(session, conversation_id, resolved_user_id)
            data_source = deepcopy(row.data_source or {})
            likes = list(data_source.get("likes", []) or [])
            likes.append([deepcopy(index), deepcopy(value), bool(liked)])
            data_source["likes"] = likes
            row.data_source = data_source
            session.add(row)
            session.commit()

    @staticmethod
    def _owner_row(
        session: Session,
        conversation_id: str,
        user_id: Any,
    ) -> Conversation:
        row = session.exec(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user == user_id,
            )
        ).one_or_none()
        if row is None:
            raise PermissionError(
                "Conversation is outside the authenticated owner scope: "
                f"conversation_id={conversation_id}"
            )
        return row


__all__ = ["RuntimeSessionMutationService"]
