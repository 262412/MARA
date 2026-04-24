from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

DEFAULT_INDEXING_STAGES = (
    "parse",
    "chunk",
    "embed",
    "vector_write",
    "docstore_write",
    "refresh",
)


@dataclass
class IndexingStage:
    name: str
    status: str = "pending"
    count: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    _started_at: float | None = field(default=None, init=False, repr=False)

    def start(self, count: int | None = None) -> "IndexingStage":
        self.status = "running"
        self.error = None
        self.duration_ms = 0.0
        self._started_at = perf_counter()
        if count is not None:
            self.count = count
        return self

    def finish(self, count: int | None = None) -> "IndexingStage":
        self.status = "completed"
        self.error = None
        self._record_duration()
        if count is not None:
            self.count = count
        return self

    def fail(
        self, error: BaseException | str, count: int | None = None
    ) -> "IndexingStage":
        self.status = "failed"
        self.error = str(error)
        self._record_duration()
        if count is not None:
            self.count = count
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "count": self.count,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }

    def _record_duration(self) -> None:
        if self._started_at is None:
            self.duration_ms = 0.0
            return

        self.duration_ms = round((perf_counter() - self._started_at) * 1000, 3)
        self._started_at = None


@dataclass
class IndexingStatus:
    stages: dict[str, IndexingStage]
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stages": {name: stage.to_dict() for name, stage in self.stages.items()},
        }


class IndexingStatusTracker:
    def __init__(self, stages: tuple[str, ...] = DEFAULT_INDEXING_STAGES):
        self._status = IndexingStatus(
            stages={stage_name: IndexingStage(stage_name) for stage_name in stages},
        )

    @property
    def status(self) -> str:
        return self._status.status

    @property
    def stages(self) -> dict[str, IndexingStage]:
        return self._status.stages

    def start(self, stage_name: str, count: int | None = None) -> IndexingStage:
        stage = self._stage(stage_name)
        stage.start(count=count)
        if self._status.status != "failed":
            self._status.status = "running"
        return stage

    def finish(self, stage_name: str, count: int | None = None) -> IndexingStage:
        stage = self._stage(stage_name)
        stage.finish(count=count)
        self._refresh_overall_status()
        return stage

    def fail(
        self,
        stage_name: str,
        error: BaseException | str,
        count: int | None = None,
    ) -> IndexingStage:
        stage = self._stage(stage_name)
        stage.fail(error=error, count=count)
        self._status.status = "failed"
        return stage

    def to_dict(self) -> dict[str, Any]:
        return self._status.to_dict()

    def _stage(self, stage_name: str) -> IndexingStage:
        try:
            return self._status.stages[stage_name]
        except KeyError as exc:
            raise ValueError(f"Unknown indexing stage: {stage_name}") from exc

    def _refresh_overall_status(self) -> None:
        if any(stage.status == "failed" for stage in self._status.stages.values()):
            self._status.status = "failed"
            return

        if all(stage.status == "completed" for stage in self._status.stages.values()):
            self._status.status = "completed"
            return

        self._status.status = "running"


def refresh_vector_store(vector_store: Any) -> str | None:
    for method_name in ("refresh", "create_fts_index", "build_index"):
        method = getattr(vector_store, method_name, None)
        if callable(method):
            method()
            return method_name

    return None
