"""Transactional coordination for deleting indexed files and external data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from .element_index import is_docstore_relation_type


@dataclass(frozen=True)
class DeletionResult:
    """Stable identifying data for one successfully deleted source."""

    file_id: str
    name: str


@dataclass(frozen=True)
class _DeletionPlan:
    file_id: str
    name: str
    user_id: str
    vector_ids: tuple[str, ...]
    docstore_ids: tuple[str, ...]
    stored_file: Path | None


class DeletionError(RuntimeError):
    """Actionable deletion failure which keeps the failed source retryable."""

    def __init__(self, *, stage: str, file_id: str, reason: str) -> None:
        self.stage = stage
        self.file_id = str(file_id)
        self.reason = _safe_reason(reason)
        super().__init__(
            f"Deletion failed at stage={self.stage} for file_id={self.file_id}: "
            f"{self.reason}"
        )


class DeletionCoordinator:
    """Delete external index data before committing relational metadata removal."""

    def __init__(
        self,
        *,
        engine: Any,
        source_table: Any,
        index_table: Any,
        vector_store: Any,
        doc_store: Any,
        file_storage_path: str | Path | None,
        session_factory: Callable[[], Session] | None = None,
        file_unlinker: Callable[[Path], None] | None = None,
    ) -> None:
        self._engine = engine
        self._source_table = source_table
        self._index_table = index_table
        self._vector_store = vector_store
        self._doc_store = doc_store
        self._storage_root = (
            Path(file_storage_path) if file_storage_path is not None else None
        )
        self._session_factory = session_factory or (lambda: Session(self._engine))
        self._file_unlinker = file_unlinker or _unlink

    def delete(self, file_id: str, *, user_id: Any) -> DeletionResult:
        """Delete one scoped source; retain its SQL rows until external success."""
        normalized_file_id = str(file_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        if not normalized_file_id or not normalized_user_id:
            raise DeletionError(
                stage="validate",
                file_id=normalized_file_id or "<missing>",
                reason="file and authenticated user identifiers are required",
            )

        plan = self._gather_plan(normalized_file_id, normalized_user_id)
        self._delete_store("vector", self._vector_store, plan.vector_ids, plan.file_id)
        self._delete_store("docstore", self._doc_store, plan.docstore_ids, plan.file_id)
        self._delete_stored_file(plan)
        self._commit_sql_deletion(plan)
        return DeletionResult(file_id=plan.file_id, name=plan.name)

    def _gather_plan(self, file_id: str, user_id: str) -> _DeletionPlan:
        try:
            with self._session_factory() as session:
                source = session.execute(
                    select(self._source_table).where(
                        self._source_table.id == file_id,
                        self._source_table.user == user_id,
                    )
                ).scalar_one_or_none()
                if source is None:
                    raise DeletionError(
                        stage="validate",
                        file_id=file_id,
                        reason="source does not exist in the authenticated user scope",
                    )
                rows = session.execute(
                    select(self._index_table).where(
                        self._index_table.source_id == file_id
                    )
                ).scalars()
                vector_ids, docstore_ids = _relation_ids(rows)
                stored_file = self._resolve_stored_file(
                    str(getattr(source, "path", "") or ""), file_id
                )
                return _DeletionPlan(
                    file_id=file_id,
                    name=str(getattr(source, "name", "") or ""),
                    user_id=user_id,
                    vector_ids=tuple(vector_ids),
                    docstore_ids=tuple(docstore_ids),
                    stored_file=stored_file,
                )
        except DeletionError:
            raise
        except Exception as exc:
            raise _stage_error("validate", file_id, exc) from exc

    def _resolve_stored_file(self, stored_path: str, file_id: str) -> Path | None:
        if not stored_path or self._storage_root is None:
            return None
        relative = Path(stored_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise DeletionError(
                stage="validate",
                file_id=file_id,
                reason="stored file path escapes the configured storage root",
            )

        root = self._storage_root.resolve(strict=False)
        candidate = self._storage_root / relative
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(root):
            raise DeletionError(
                stage="validate",
                file_id=file_id,
                reason="stored file symlink escapes the configured storage root",
            )
        return candidate

    def _delete_store(
        self, stage: str, store: Any, target_ids: tuple[str, ...], file_id: str
    ) -> None:
        if not target_ids or store is None:
            return
        for target_id in target_ids:
            try:
                store.delete([target_id])
            except Exception as exc:
                if _is_missing_error(exc):
                    continue
                raise _stage_error(stage, file_id, exc) from exc

    def _delete_stored_file(self, plan: _DeletionPlan) -> None:
        candidate = plan.stored_file
        if candidate is None or (not candidate.exists() and not candidate.is_symlink()):
            return
        if candidate.is_dir() and not candidate.is_symlink():
            raise DeletionError(
                stage="disk",
                file_id=plan.file_id,
                reason="stored file path unexpectedly refers to a directory",
            )
        try:
            self._file_unlinker(candidate)
        except Exception as exc:
            if _is_missing_error(exc):
                return
            raise _stage_error("disk", plan.file_id, exc) from exc

    def _commit_sql_deletion(self, plan: _DeletionPlan) -> None:
        try:
            with self._session_factory() as session:
                session.execute(
                    delete(self._index_table).where(
                        self._index_table.source_id == plan.file_id
                    )
                )
                result = cast(
                    CursorResult[Any],
                    session.execute(
                        delete(self._source_table).where(
                            self._source_table.id == plan.file_id,
                            self._source_table.user == plan.user_id,
                        )
                    ),
                )
                if result.rowcount != 1:
                    session.rollback()
                    raise DeletionError(
                        stage="sql",
                        file_id=plan.file_id,
                        reason="source scope changed before relational commit",
                    )
                session.commit()
        except DeletionError:
            raise
        except Exception as exc:
            raise _stage_error("sql", plan.file_id, exc) from exc


def _relation_ids(rows: Any) -> tuple[list[str], list[str]]:
    vector_ids: list[str] = []
    docstore_ids: list[str] = []
    for row in rows:
        relation_type = str(getattr(row, "relation_type", "") or "")
        target_id = str(getattr(row, "target_id", "") or "")
        if not target_id:
            continue
        if relation_type == "vector":
            vector_ids.append(target_id)
        elif is_docstore_relation_type(relation_type):
            docstore_ids.append(target_id)
    return vector_ids, docstore_ids


def _unlink(path: Path) -> None:
    path.unlink()


def _is_missing_error(exc: Exception) -> bool:
    if isinstance(exc, (FileNotFoundError, KeyError)):
        return True
    status = getattr(exc, "status_code", None)
    code = str(getattr(exc, "code", "") or "").strip().lower()
    return status == 404 or code in {"404", "not_found", "not-found"}


def _safe_reason(reason: object) -> str:
    text = " ".join(str(reason or "unknown error").split())
    return text[:300]


def _stage_error(stage: str, file_id: str, exc: Exception) -> DeletionError:
    return DeletionError(
        stage=stage,
        file_id=file_id,
        reason=f"{type(exc).__name__}: {_safe_reason(exc)}",
    )
