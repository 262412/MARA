from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import CancelledError, Future
from contextlib import contextmanager
from functools import wraps
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
        if isinstance(primary, StopIteration):
            primary = None
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
        self._startup_lock = threading.Lock()
        self._producer_entered = False
        self._start_failed = False
        self.thread = threading.Thread(
            target=self._consume, args=(factory,), daemon=True
        )

    def _consume(self, factory: Callable[[], Iterable[Any]]) -> None:
        with self._startup_lock:
            if self._start_failed:
                return
            self._producer_entered = True
        try:
            with owned_iterator(iter(factory())) as iterator:
                while not self.stop_requested.is_set():
                    try:
                        next(iterator)
                    except StopIteration:
                        break
                if self.stop_requested.is_set():
                    raise CancelledError("Artifact writer stopped before completion")
        except CancelledError as exc:
            self.set_exception(exc)
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

    def abort_start(self, error: BaseException) -> None:
        with self._startup_lock:
            self._start_failed = True
            self.stop_requested.set()
            if not self._producer_entered:
                # A late native bootstrap must return without opening the input.
                self.set_exception(error)
        if self.thread.ident is not None:
            self.thread.join()


def _close_writer(writer: Future[None] | None) -> None:
    if writer is None:
        return
    primary = sys.exc_info()[1]
    if isinstance(writer, _ArtifactWriter):
        writer.stop_requested.set()
        writer.thread.join()
    try:
        writer.result()
    except BaseException as exc:
        if isinstance(exc, CancelledError) and isinstance(writer, _ArtifactWriter):
            return
        if primary is None:
            raise
        if exc is not primary:
            logger.exception("Artifact writer cleanup failed during %r", primary)


def indexing_run(stream: Callable) -> Callable:
    """Compatibility facade: keep a single run's writer owned through stream exit."""

    @wraps(stream)
    def generate(pipeline: Any, *args: Any, **kwargs: Any):
        lock = vars(pipeline).setdefault("_artifact_run_lock", threading.Lock())
        if not lock.acquire(blocking=False):
            raise RuntimeError("Cannot replace an active indexing run")
        try:
            _check_writer_available(pipeline)
            try:
                with owned_iterator(stream(pipeline, *args, **kwargs)) as iterator:
                    while True:
                        try:
                            item = next(iterator)
                        except StopIteration as stopped:
                            return stopped.value
                        yield item
            finally:
                _close_writer(getattr(pipeline, "_artifact_writer_future", None))
        finally:
            lock.release()

    return generate


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
        future.abort_start(exc)
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
        if isinstance(writer, _ArtifactWriter):
            writer.thread.join()
    return pipeline.finish(file_id, source_path)


__all__ = [
    "begin_artifact_generation",
    "begin_indexing_artifacts",
    "consume_in_background",
    "finish_indexing",
    "indexing_run",
    "owned_iterator",
    "schedule_writer",
    "strip_artifact_generation",
]
