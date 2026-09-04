from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Literal, Protocol

from .query_readiness import QueryFailureContract, classify_query_failure

STREAM_POLL_INTERVAL = 0.05
LOGGER = logging.getLogger("mara.desktop.query_stream")


class QueryService(Protocol):
    def validate_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
    ) -> dict[str, Any] | None:
        ...

    def stream_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
        cancel_event: threading.Event,
        *,
        turn_id: str,
    ) -> Iterator[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class QueryStreamOutcome:
    status: Literal["success", "failed", "cancelled", "timeout"]
    error: QueryFailureContract | None = None


class QueryStreamRunner:
    def __init__(self, service: QueryService, *, idle_timeout: float) -> None:
        self._service = service
        self._idle_timeout = idle_timeout

    def run(
        self,
        task_id: str,
        turn_id: str,
        arguments: tuple[str, str, list[str]],
        cancel_event: threading.Event,
        on_update: Callable[[dict[str, Any]], bool],
    ) -> QueryStreamOutcome:
        messages: Queue[tuple[str, Any]] = Queue()
        threading.Thread(
            target=self._produce,
            args=(task_id, turn_id, arguments, cancel_event, messages),
            daemon=True,
            name=f"mara-query-runtime-{task_id[:8]}",
        ).start()
        completed = False
        last_update = time.monotonic()
        while True:
            if cancel_event.is_set() and messages.empty():
                return QueryStreamOutcome("cancelled")
            remaining = self._idle_timeout - (time.monotonic() - last_update)
            if remaining <= 0:
                cancel_event.set()
                return QueryStreamOutcome("timeout")
            try:
                kind, payload = messages.get(
                    timeout=(
                        0
                        if cancel_event.is_set()
                        else min(STREAM_POLL_INTERVAL, remaining)
                    )
                )
            except Empty:
                continue
            if kind == "error":
                return QueryStreamOutcome("failed", payload)
            if kind == "done":
                return QueryStreamOutcome("success" if completed else "failed")
            last_update = time.monotonic()
            completed = bool(payload.get("final", False))
            if not on_update(payload):
                cancel_event.set()
                return QueryStreamOutcome("cancelled")

    def _produce(
        self,
        task_id: str,
        turn_id: str,
        arguments: tuple[str, str, list[str]],
        cancel_event: threading.Event,
        messages: Queue[tuple[str, Any]],
    ) -> None:
        stream: Iterator[dict[str, Any]] | None = None
        try:
            stream = self._service.stream_query(
                *arguments,
                cancel_event,
                turn_id=turn_id,
            )
            for update in stream:
                if cancel_event.is_set():
                    break
                messages.put(("update", update))
            messages.put(("done", None))
        except Exception as error:
            failure = classify_query_failure(error)
            LOGGER.error(
                "Query runtime stream failed task_id=%s error_code=%s stage=%s error_type=%s",
                task_id,
                failure.code,
                "streaming",
                type(error).__name__,
            )
            messages.put(("error", failure))
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
