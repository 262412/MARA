from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from typing import Any, Callable, Iterable
from uuid import uuid4

logger = logging.getLogger(__name__)


def begin_artifact_generation(pipeline: Any, extra_info: dict) -> str:
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
    pipeline._artifact_generation = None
    pipeline._artifact_writer_future = None
    return None


def strip_artifact_generation(documents: list[Any]) -> list[Any]:
    for document in documents:
        document.metadata.pop("artifact_generation", None)
    return documents


def consume_in_background(factory: Callable[[], Iterable[Any]]) -> Future[None]:
    future: Future[None] = Future()

    def consume() -> None:
        try:
            list(factory())
        except BaseException as exc:
            logger.exception("Artifact background writer failed")
            error = (
                exc
                if isinstance(exc, Exception)
                else RuntimeError(
                    f"Artifact background writer terminated: {type(exc).__name__}"
                )
            )
            future.set_exception(error)
        else:
            future.set_result(None)

    threading.Thread(target=consume, daemon=True).start()
    return future


def schedule_writer(
    pipeline: Any,
    factory: Callable[[], Iterable[Any]],
) -> Iterable[Any]:
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
    "schedule_writer",
    "strip_artifact_generation",
]
