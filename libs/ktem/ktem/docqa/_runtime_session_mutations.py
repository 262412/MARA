from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from ktem.db.models import Conversation
from sqlmodel import Session, select


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
