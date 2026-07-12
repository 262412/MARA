"""Transactional coordination for deleting indexed files and external data."""

from __future__ import annotations

import logging
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from .element_index import is_docstore_relation_type
from .storage_lifetime import QuarantineMove, StorageLease, StorageLifetime

logger = logging.getLogger(__name__)


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
    stored_path: str | None


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
    """Delete external data before atomically releasing relational file ownership."""

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
        file_mover: Callable[[Path, Path], None] | None = None,
        file_unlinker: Callable[[Path], None] | None = None,
        storage_lifetime: Any | None = None,
        artifact_cleaner: Callable[[str], None] | None = None,
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
        self._artifact_cleaner = artifact_cleaner
        self._storage_lifetime = storage_lifetime
        if self._storage_lifetime is None and self._storage_root is not None:
            self._storage_lifetime = StorageLifetime(
                self._storage_root,
                mover=file_mover,
                unlinker=file_unlinker,
            )

    def delete(self, file_id: str, *, user_id: Any) -> DeletionResult:
        """Delete one scoped source; retain SQL rows until external success."""
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
        self._delete_artifacts(plan.file_id)
        self._delete_relational_and_storage(plan)
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
                stored_path = self._validate_stored_path(
                    str(getattr(source, "path", "") or ""), file_id
                )
                return _DeletionPlan(
                    file_id=file_id,
                    name=str(getattr(source, "name", "") or ""),
                    user_id=user_id,
                    vector_ids=tuple(vector_ids),
                    docstore_ids=tuple(docstore_ids),
                    stored_path=stored_path,
                )
        except DeletionError:
            raise
        except Exception as exc:
            raise _stage_error("validate", file_id, exc) from exc

    def _validate_stored_path(self, stored_path: str, file_id: str) -> str | None:
        if not stored_path or self._storage_root is None:
            return None
        relative = Path(stored_path)
        if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
            raise DeletionError(
                stage="validate",
                file_id=file_id,
                reason="stored file path escapes the configured storage root",
            )
        _validate_existing_storage_path(self._storage_root, relative, file_id)
        return str(relative)

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

    def _delete_artifacts(self, file_id: str) -> None:
        if self._artifact_cleaner is None:
            return
        try:
            self._artifact_cleaner(file_id)
        except Exception as exc:
            raise _stage_error("artifacts", file_id, exc) from exc

    def _delete_relational_and_storage(self, plan: _DeletionPlan) -> None:
        if plan.stored_path is None or self._storage_lifetime is None:
            self._commit_under_lease(plan, None)
            return
        try:
            with self._storage_lifetime.hold(plan.stored_path) as lease:
                self._commit_under_lease(plan, lease)
        except DeletionError:
            raise
        except Exception as exc:
            raise _stage_error("disk", plan.file_id, exc) from exc

    def _commit_under_lease(
        self, plan: _DeletionPlan, lease: StorageLease | None
    ) -> None:
        move: QuarantineMove | None = None
        try:
            with self._session_factory() as session:
                self._delete_sql_rows(session, plan)
                if lease is not None and self._remaining_references(session, plan) == 0:
                    try:
                        move = lease.quarantine()
                    except Exception as exc:
                        session.rollback()
                        raise _stage_error("disk", plan.file_id, exc) from exc
                try:
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    reason = self._restore_reason(lease, move, exc)
                    raise DeletionError(
                        stage="sql", file_id=plan.file_id, reason=reason
                    ) from exc
        except DeletionError:
            raise
        except Exception as exc:
            raise _stage_error("sql", plan.file_id, exc) from exc

        if lease is not None and move is not None:
            try:
                lease.purge(move)
            except Exception:
                logger.exception(
                    "Committed deletion left auditable storage orphan file_id=%s "
                    "orphan=%s",
                    plan.file_id,
                    move.quarantine,
                )

    def _delete_sql_rows(self, session: Session, plan: _DeletionPlan) -> None:
        index_conditions = [self._index_table.source_id == plan.file_id]
        if hasattr(self._index_table, "user"):
            index_conditions.append(self._index_table.user == plan.user_id)
        session.execute(delete(self._index_table).where(*index_conditions))
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
        session.flush()

    def _remaining_references(self, session: Session, plan: _DeletionPlan) -> int:
        if plan.stored_path is None:
            return 0
        count = session.scalar(
            select(func.count())
            .select_from(self._source_table)
            .where(self._source_table.path == plan.stored_path)
        )
        return int(count or 0)

    @staticmethod
    def _restore_reason(
        lease: StorageLease | None,
        move: QuarantineMove | None,
        commit_error: Exception,
    ) -> str:
        reason = f"{type(commit_error).__name__}: {_safe_reason(commit_error)}"
        if lease is None or move is None:
            return reason
        try:
            lease.restore(move)
        except Exception as restore_error:
            logger.exception("Failed to restore quarantined source after SQL failure")
            return (
                f"{reason}; restore failed: {type(restore_error).__name__}: "
                f"{_safe_reason(restore_error)}"
            )
        return reason


def _validate_existing_storage_path(root: Path, relative: Path, file_id: str) -> None:
    current = root
    parts = relative.parts
    for position, part in enumerate(("", *parts)):
        if part:
            current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise DeletionError(
                stage="validate",
                file_id=file_id,
                reason="stored file path contains a symlink",
            )
        if position < len(parts) and not stat.S_ISDIR(mode):
            raise DeletionError(
                stage="validate",
                file_id=file_id,
                reason="stored file parent is not a directory",
            )
        if position == len(parts) and not stat.S_ISREG(mode):
            raise DeletionError(
                stage="disk",
                file_id=file_id,
                reason="stored file path is not a regular file",
            )


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


__all__ = ["DeletionCoordinator", "DeletionError", "DeletionResult"]
