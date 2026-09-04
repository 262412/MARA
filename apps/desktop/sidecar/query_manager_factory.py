from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from .query_stream_runner import QueryService
from .query_task_journal import JsonQueryTaskJournal
from .query_tasks import QueryTaskManager
from .smoke_faults import inject_query_smoke_fault


def create_query_task_manager(
    service: Any,
    existing: QueryTaskManager | None,
    journal_path: Path | None,
    smoke_fault_marker: Path | None,
) -> QueryTaskManager:
    if existing is not None:
        return existing
    journal = inject_query_smoke_fault(
        JsonQueryTaskJournal(journal_path),
        smoke_fault_marker,
    )
    return QueryTaskManager(cast(QueryService, service), journal=journal)
