from __future__ import annotations

import html
from typing import Any, Callable

from ktem.utils.render import Render
from sqlalchemy import select
from sqlalchemy.orm import Session


class FileSelectionError(PermissionError):
    pass


class FileSelectionService:
    def __init__(
        self,
        *,
        index: Any,
        engine: Any,
        sort_key: Callable[[Any], Any],
    ) -> None:
        self._index = index
        self._engine = engine
        self._sort_key = sort_key

    def render_chunks(self, file_id: str, user_id: Any = None) -> str:
        self._require_file_access(file_id, user_id)
        documents = sorted(
            self._documents_for_file(file_id),
            key=self._sort_key,
        )
        return "".join(
            self._render_document(document, position, len(documents))
            for position, document in enumerate(documents, start=1)
        )

    def source_name(self, file_id: str, user_id: Any = None) -> str:
        return str(self._require_file_access(file_id, user_id).name)

    def _require_file_access(self, file_id: str, user_id: Any) -> Any:
        source_table = self._index._resources["Source"]
        statement = select(source_table).where(source_table.id == file_id)
        if self._index.config.get("private", False):
            statement = statement.where(source_table.user == user_id)
        with Session(self._engine) as session:
            match = session.execute(statement).first()
        if match is None:
            raise FileSelectionError(
                "File is outside the authenticated user scope: " f"file_id={file_id}"
            )
        return match[0]

    def _documents_for_file(self, file_id: str) -> list[Any]:
        index_table = self._index._resources["Index"]
        with Session(self._engine) as session:
            matches = session.execute(
                select(index_table).where(
                    index_table.source_id == file_id,
                    index_table.relation_type == "document",
                )
            )
            document_ids = [record.target_id for (record,) in matches]
        return list(self._index._docstore.get(document_ids))

    @staticmethod
    def _render_document(document: Any, position: int, total: int) -> str:
        text = str(document.text or "")
        title = html.escape(f"{text[:50]}..." if len(text) > 50 else text)
        document_type = document.metadata.get("type", "text")
        if document_type == "table":
            content = Render.table(text)
        elif document_type == "image":
            content = Render.image(
                url=document.metadata.get("image_origin", ""),
                text=text,
            )
        else:
            content = html.escape(text)

        header = f"[{position}/{total}]"
        if document.metadata.get("page_label"):
            header += f" [Page {document.metadata['page_label']}]"
        return Render.collapsible(header=f"{header} {title}", content=content)


__all__ = ["FileSelectionError", "FileSelectionService"]
