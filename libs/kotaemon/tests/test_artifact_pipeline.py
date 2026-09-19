from concurrent.futures import Future
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from kotaemon import artifact_pipeline as artifacts


def test_sync_writer_is_lazy_and_keeps_iterator_return():
    calls = []

    def produce():
        calls.append("write")
        yield "progress"
        return "writer return"

    pipeline = SimpleNamespace(run_embedding_in_thread=False)
    iterator = artifacts.schedule_writer(pipeline, produce)
    assert calls == []
    assert pipeline._artifact_writer_future is None
    assert next(iterator) == "progress"
    with pytest.raises(StopIteration) as stopped:
        next(iterator)
    assert stopped.value.value == "writer return"
    assert calls == ["write"]


@pytest.mark.parametrize("enabled", [True, False])
def test_generation_and_finish_facades_preserve_metadata_and_result(enabled):
    calls = []
    pipeline = SimpleNamespace(finish=lambda *args: calls.append(args) or "finished")
    metadata = {"file_id": "owner", "nested": {"keep": True}}
    nested = metadata["nested"]
    generation = artifacts.begin_indexing_artifacts(pipeline, metadata, enabled=enabled)
    assert pipeline._artifact_generation == generation
    assert pipeline._artifact_writer_future is None
    assert metadata["nested"] is nested
    assert (metadata.get("artifact_generation") is not None) is enabled
    assert artifacts.finish_indexing(pipeline, "owner", "input") == "finished"
    assert calls == [("owner", "input")]


def test_background_completion_precedes_finish_with_real_thread():
    entered, release, stopped, waiting = (Event() for _ in range(4))
    calls = []
    threads = []

    def produce():
        from threading import current_thread

        threads.append(current_thread())
        entered.set()
        try:
            assert release.wait(5)
            calls.append("write")
            yield "hidden progress"
        finally:
            calls.append("iterator closed")
            stopped.set()

    pipeline = SimpleNamespace(
        run_embedding_in_thread=True,
        finish=lambda *args: calls.append("finish"),
    )
    assert artifacts.schedule_writer(pipeline, produce) == ()
    writer = pipeline._artifact_writer_future
    assert isinstance(writer, Future)
    original_result = writer.result

    def observed_result(*args, **kwargs):
        waiting.set()
        return original_result(*args, **kwargs)

    writer.result = observed_result
    finalizer = Thread(target=artifacts.finish_indexing, args=(pipeline, "id", "path"))
    try:
        assert entered.wait(5)
        finalizer.start()
        assert waiting.wait(5)
        assert calls == []
    finally:
        release.set()
        finalizer.join(5)
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
    assert stopped.is_set()
    assert not finalizer.is_alive()
    assert calls == ["write", "iterator closed", "finish"]


@pytest.mark.parametrize("stage", ["factory", "iteration"])
def test_background_error_identity_blocks_finish(stage):
    error = ValueError("writer failed")
    threads = []

    def produce():
        from threading import current_thread

        threads.append(current_thread())
        if stage == "factory":
            raise error

        def iterator():
            yield "partial write"
            raise error

        return iterator()

    pipeline = SimpleNamespace(
        run_embedding_in_thread=True, finish=lambda *_: pytest.fail()
    )
    artifacts.schedule_writer(pipeline, produce)
    try:
        with pytest.raises(ValueError) as caught:
            artifacts.finish_indexing(pipeline, "id", "path")
        assert caught.value is error
    finally:
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
