from __future__ import annotations

from typing import Any

from ktem.db.models import engine

from ._runtime_session_mutations import RuntimeSessionMutationService


class RuntimeSessionMutationFacade:
    def _resolve_user_id(self, user_id: Any = None):
        raise NotImplementedError

    def _get_session_mutation_service(self) -> RuntimeSessionMutationService:
        return RuntimeSessionMutationService(
            engine=engine,
            resolve_user_id=self._resolve_user_id,
        )

    def delete_session(self, conversation_id: str, user_id: Any = None) -> None:
        self._get_session_mutation_service().delete_session(conversation_id, user_id)

    def rename_session(
        self,
        conversation_id: str,
        name: str,
        user_id: Any = None,
    ) -> None:
        self._get_session_mutation_service().rename_session(
            conversation_id,
            name,
            user_id,
        )

    def update_chat_suggestions(
        self,
        conversation_id: str,
        suggestions: list[str],
        user_id: Any = None,
    ) -> None:
        self._get_session_mutation_service().update_chat_suggestions(
            conversation_id,
            suggestions,
            user_id,
        )


__all__ = ["RuntimeSessionMutationFacade"]
