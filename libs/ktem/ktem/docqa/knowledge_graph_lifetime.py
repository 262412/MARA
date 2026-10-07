"""Short graph snapshots/publications coordinated with Source and Conversation.

Build/model work runs outside every lease and SQL Session. Sidecar receipts are
rebuildable cache metadata, never changes to persisted conversation schemas.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from ktem.db.models import Conversation
from ktem.index.file.source_writes import source_lock
from ktem.index.file.storage_lifetime import _ensure_real_directory
from sqlmodel import Session, select

from .conversation_lifetime import conversation_write
from .knowledge_graph_cache import load_snapshot, save_snapshot


class GraphCacheInvalidated(RuntimeError):
    """The build no longer represents the authorized current input."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class GraphCacheRequest:
    def __init__(
        self,
        root: Path,
        engine: Any,
        index: Any,
        conversation_id: str,
        user_id: str,
        sources: dict[str, Any],
        *,
        owner_required: bool,
        register: bool = True,
    ) -> None:
        self.engine, self.index = engine, index
        self.conversation_id, self.user_id = str(conversation_id or "draft"), user_id
        self.sources, self.owner_required = sources, owner_required
        self.draft = self.conversation_id == "draft"
        self.register = register
        self.token = uuid4().hex
        self.receipt = root / (".request-" + _digest(self.conversation_id) + ".json")
        self.metadata = root / (".snapshot-" + _digest(self.conversation_id) + ".json")
        _ensure_real_directory(root)
        with self._locks():
            self.version, self.conversation = self._snapshot()
            if not self.draft and self.register:
                save_snapshot(self.receipt, {"token": self.token})

    @contextmanager
    def _locks(self) -> Iterator[None]:
        with ExitStack() as stack:
            source_table = self.index._resources["Source"]
            for file_id in sorted(self.sources):
                stack.enter_context(source_lock(self.engine, source_table, file_id))
            stack.enter_context(conversation_write(self.engine, self.conversation_id))
            yield

    def _snapshot(self) -> tuple[str, str]:
        resources = self.index._resources
        table, index_table = resources["Source"], resources["Index"]
        stamps = []
        with Session(self.engine) as session:
            conversation = self._conversation_snapshot(session)
            for file_id, expected in self.sources.items():
                row = session.get(table, file_id)
                if row is None or (
                    self.owner_required and str(row.user or "") != self.user_id
                ):
                    raise GraphCacheInvalidated("Graph source is no longer available")
                actual = {
                    "id": str(row.id),
                    "name": row.name or str(row.id),
                    "path": row.path,
                    "size": row.size,
                    "date_created": str(row.date_created or ""),
                }
                if actual != expected:
                    raise GraphCacheInvalidated(
                        "Graph source changed during construction"
                    )
                relations = session.execute(
                    select(index_table.target_id, index_table.relation_type).where(
                        index_table.source_id == file_id
                    )
                ).all()
                stamps.append([actual, sorted(tuple(item) for item in relations)])
        scope = [self.index.id, table.__table__.fullname, self.user_id, stamps]
        return _digest(scope), conversation

    def _conversation_snapshot(self, session: Session) -> str:
        if self.draft:
            return "draft"
        row = session.get(Conversation, self.conversation_id)
        if row is None or (str(row.user) != self.user_id and not row.is_public):
            raise PermissionError("Graph conversation is unavailable")
        data = row.data_source or {}
        return _digest(
            [
                row.id,
                row.user,
                row.is_public,
                row.date_created,
                data.get("graph_source_ids"),
                data.get("selected"),
            ]
        )

    @contextmanager
    def current(self) -> Iterator[None]:
        with self._locks():
            if self._snapshot() != (self.version, self.conversation):
                raise GraphCacheInvalidated("Graph input changed during construction")
            if (
                not self.draft
                and self.register
                and load_snapshot(self.receipt, {}).get("token") != self.token
            ):
                raise GraphCacheInvalidated(
                    "A newer graph request superseded this build"
                )
            yield

    def cache_matches(self, state: dict[str, Any]) -> bool:
        if self.draft:
            return False
        metadata = load_snapshot(self.metadata, {})
        return metadata == {"version": self.version, "state": _digest(state)}

    def record_publication(self, state: dict[str, Any]) -> None:
        # The snapshot has already been replaced. A failure here leaves a
        # published but unverified snapshot, rejected on the next read.
        save_snapshot(self.metadata, {"version": self.version, "state": _digest(state)})


def begin_graph_request(
    root: Path,
    engine: Any,
    index: Any,
    conversation_id: str,
    user_id: str,
    sources: dict[str, Any],
    *,
    owner_required: bool,
) -> GraphCacheRequest:
    return GraphCacheRequest(
        root,
        engine,
        index,
        conversation_id,
        user_id,
        sources,
        owner_required=owner_required,
    )


def resolve_graph_view(
    request: GraphCacheRequest,
    conversation_id: str,
    manifest: dict[str, str],
    schema_version: int,
    *,
    force_rebuild: bool,
    load: Callable,
    save: Callable,
    build: Callable,
    graph_schema: Callable,
) -> tuple[dict[str, Any] | None, str, bool]:
    """Read/publish under short leases; invoke the unchanged builder outside."""
    with request.current():
        state = {} if request.draft else load(conversation_id)
        valid = request.cache_matches(state)
    cached_graph = state.get("graph")
    matching = (state.get("manifest", {}) or {}) == manifest
    cached_schema = int(state.get("schema_version") or graph_schema(cached_graph) or 0)
    outdated = bool(cached_graph) and matching and cached_schema != schema_version
    if force_rebuild:
        graph = build()
        state = {
            "conversation_id": conversation_id,
            "schema_version": schema_version,
            "manifest": manifest,
            "graph": graph,
        }
        with request.current():
            if not request.draft:
                save(conversation_id, state)
                request.record_publication(state)
        return graph, "ready", outdated
    graph = cached_graph if valid and isinstance(cached_graph, dict) else None
    fresh = bool(graph) and matching and cached_schema == schema_version
    return graph, "ready" if fresh else "stale", outdated
