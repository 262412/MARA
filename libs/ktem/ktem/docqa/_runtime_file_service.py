from __future__ import annotations

from typing import Any, Callable, Optional, cast

from ktem.index.file.deletion import DeletionCoordinator

from . import _runtime_indexing as _indexing
from . import _runtime_selection as _selection
from ._runtime_models import DocQAFileRecord, DocQAIndexResult


class RuntimeFileService:
    def __init__(
        self,
        *,
        file_index: Any,
        engine: Any,
        resolve_user_id: Callable[[Any], Any],
        load_settings: Callable[[Any], dict[str, Any]],
        zip_input_dir: str,
        deletion_coordinator_cls: Any = DeletionCoordinator,
    ) -> None:
        self._file_index = file_index
        self._engine = engine
        self._resolve_user_id = resolve_user_id
        self._load_settings = load_settings
        self._zip_input_dir = zip_input_dir
        self._deletion_coordinator_cls = deletion_coordinator_cls

    def list_files(self, user_id: Any = None) -> list[DocQAFileRecord]:
        if not self._file_index:
            return []

        resolved_user_id = self._resolve_user_id(user_id)
        rows = self._file_index.list_source_rows(resolved_user_id)
        return [self._file_record(row) for row in rows]

    @staticmethod
    def _file_record(row: dict[str, Any]) -> DocQAFileRecord:
        return DocQAFileRecord(
            file_id=str(row.get("id", "") or ""),
            name=str(row.get("name", "") or ""),
            size=int(row.get("size", 0) or 0),
            tokens=int((row.get("note", {}) or {}).get("tokens", 0) or 0),
            loader=str((row.get("note", {}) or {}).get("loader", "") or ""),
            path=str(row.get("path", "") or ""),
            date_created=row.get("date_created"),
        )

    def resolve_file_refs(
        self,
        refs: list[str],
        user_id: Any = None,
    ) -> list[DocQAFileRecord]:
        records = self.list_files(user_id=user_id)
        return cast(list[DocQAFileRecord], _selection.resolve_file_refs(records, refs))

    def expand_zip_inputs(self, paths: list[str]) -> list[str]:
        return _indexing.expand_zip_inputs(
            self._file_index,
            paths,
            zip_input_dir=self._zip_input_dir,
        )

    def expand_index_inputs(self, paths: list[str]) -> list[str]:
        return _indexing.expand_index_inputs(
            self._file_index,
            paths,
            zip_input_dir=self._zip_input_dir,
        )

    def index_paths(
        self,
        paths: list[str],
        reindex: bool = False,
        user_id: Any = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> DocQAIndexResult:
        return _indexing.index_paths(
            self._file_index,
            paths,
            reindex=reindex,
            settings=settings,
            load_settings=self._load_settings,
            resolve_user_id=self._resolve_user_id,
            user_id=user_id,
            zip_input_dir=self._zip_input_dir,
        )

    def delete_files(
        self,
        refs: list[str],
        user_id: Any = None,
    ) -> list[DocQAFileRecord]:
        if not self._file_index:
            return []

        resolved_user_id = self._resolve_user_id(user_id)
        matches = self.resolve_file_refs(refs, user_id=resolved_user_id)
        resources = self._file_index._resources
        coordinator = self._deletion_coordinator_cls(
            engine=self._engine,
            source_table=resources["Source"],
            index_table=resources["Index"],
            vector_store=resources["VectorStore"],
            doc_store=resources["DocStore"],
            file_storage_path=resources.get("FileStoragePath"),
        )
        for match in matches:
            coordinator.delete(match.file_id, user_id=resolved_user_id)
        return matches


__all__ = ["RuntimeFileService"]
