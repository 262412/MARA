from __future__ import annotations

from typing import Any

from ktem.db.models import engine

from ._runtime_session_mutations import RuntimeSessionMutationService
from ._runtime_session_service import RuntimeSessionService


class RuntimeSessionMutationFacade:
    def _resolve_user_id(self, user_id: Any = None):
        raise NotImplementedError

    def _get_session_mutation_service(self) -> RuntimeSessionMutationService:
        return RuntimeSessionMutationService(
            engine=engine,
            resolve_user_id=self._resolve_user_id,
        )

    def _get_session_service(self) -> RuntimeSessionService:
        raise NotImplementedError

    def load_graph_source_ids(
        self,
        conversation_id: str,
        user_id: Any = None,
    ) -> list[str]:
        return self._get_session_service().load_graph_source_ids(
            conversation_id,
            user_id=user_id,
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

    def set_session_public(
        self,
        conversation_id: str,
        is_public: bool,
        user_id: Any = None,
    ) -> str:
        return self._get_session_mutation_service().set_session_public(
            conversation_id,
            is_public,
            user_id,
        )

    def persist_graph_source_ids(
        self,
        conversation_id: str,
        source_ids: list[str],
        user_id: Any = None,
    ) -> list[str]:
        return self._get_session_mutation_service().persist_graph_source_ids(
            conversation_id,
            source_ids,
            user_id,
        )

    def append_session_like(
        self,
        conversation_id: str,
        index: Any,
        value: Any,
        liked: bool,
        user_id: Any = None,
    ) -> None:
        self._get_session_mutation_service().append_session_like(
            conversation_id,
            index,
            value,
            liked,
            user_id,
        )


__all__ = ["RuntimeSessionMutationFacade"]
