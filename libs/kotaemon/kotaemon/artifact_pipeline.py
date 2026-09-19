from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import Future
from contextlib import contextmanager
from typing import Any, Callable, Iterable
from uuid import uuid4

logger = logging.getLogger(__name__)


@contextmanager
def owned_iterator(iterator: Any):
    """Close an iterator created by this consumer, preserving its primary error."""
    try:
        yield iterator
    finally:
        primary = sys.exc_info()[1]
        close = getattr(iterator, "close", None)
        if close is not None:
            try:
                close()
            except BaseException:
                if primary is None:
                    raise
                logger.exception("Indexing iterator cleanup failed during %r", primary)


class _ArtifactWriter(Future[None]):
    """One producer owns its iterator; Future completion is not thread termination."""

    def __init__(self, factory: Callable[[], Iterable[Any]]) -> None:
        super().__init__()
        self.stop_requested = threading.Event()
        self.thread = threading.Thread(
            target=self._consume, args=(factory,), daemon=True
        )

    def _consume(self, factory: Callable[[], Iterable[Any]]) -> None:
        try:
            with owned_iterator(iter(factory())) as iterator:
                while not self.stop_requested.is_set():
                    try:
                        next(iterator)
                    except StopIteration:
                        break
        except BaseException as exc:
            logger.exception("Artifact background writer failed")
            error = (
                exc
                if isinstance(exc, Exception)
                else RuntimeError(
                    f"Artifact background writer terminated: {type(exc).__name__}"
                )
            )
            self.set_exception(error)
        else:
            self.set_result(None)


def _check_writer_available(pipeline: Any) -> None:
    writer = getattr(pipeline, "_artifact_writer_future", None)
    if writer is not None and (
        writer.thread.is_alive()
        if isinstance(writer, _ArtifactWriter)
        else not writer.done()
    ):
        raise RuntimeError("Cannot replace an active artifact writer")


def begin_artifact_generation(pipeline: Any, extra_info: dict) -> str:
    _check_writer_available(pipeline)
    generation = uuid4().hex
    pipeline._artifact_generation = generation
    pipeline._artifact_writer_future = None
    extra_info["artifact_generation"] = generation
    return generation


def begin_indexing_artifacts(
    pipeline: Any,
    extra_info: dict,
    *,
    enabled: bool,
) -> str | None:
    if enabled:
        return begin_artifact_generation(pipeline, extra_info)
    _check_writer_available(pipeline)
    pipeline._artifact_generation = None
    pipeline._artifact_writer_future = None
    return None


def strip_artifact_generation(documents: list[Any]) -> list[Any]:
    for document in documents:
        document.metadata.pop("artifact_generation", None)
    return documents


def consume_in_background(factory: Callable[[], Iterable[Any]]) -> Future[None]:
    future = _ArtifactWriter(factory)
    future.set_running_or_notify_cancel()
    try:
        future.thread.start()
    except BaseException as exc:
        future.set_exception(exc)
        raise
    return future


def schedule_writer(
    pipeline: Any,
    factory: Callable[[], Iterable[Any]],
) -> Iterable[Any]:
    _check_writer_available(pipeline)
    if pipeline.run_embedding_in_thread:
        logger.debug("Running embedding in background thread")
        pipeline._artifact_writer_future = consume_in_background(factory)
        return ()
    pipeline._artifact_writer_future = None
    return factory()


def finish_indexing(pipeline: Any, file_id: object, source_path: object) -> Any:
    writer = getattr(pipeline, "_artifact_writer_future", None)
    if writer is not None:
        writer.result()
    return pipeline.finish(file_id, source_path)


__all__ = [
    "begin_artifact_generation",
    "begin_indexing_artifacts",
    "consume_in_background",
    "finish_indexing",
    "owned_iterator",
    "schedule_writer",
    "strip_artifact_generation",
]
