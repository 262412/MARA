import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from ktem.index.file import pipelines

from kotaemon import artifact_pipeline as artifacts
from kotaemon.base import Document


def subject(monkeypatch, handle):
    monkeypatch.setattr(
        pipelines.settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", False, raising=False
    )
    calls = []

    def store(path):
        calls.append("source")
        return "file"

    pipeline = SimpleNamespace(
        collection_name="owned",
        source_write_scope=lambda _file_id: nullcontext(),
        run_embedding_in_thread=True,
        get_id_if_exists=lambda path: calls.append("lookup"),
        store_url=store,
        load_docs_with_parse_cache=lambda *a: SimpleNamespace(
            documents=[], cache_hit=False, stats={}
        ),
        handle_docs=handle,
        finish=lambda *a: calls.append("finish"),
    )
    return pipeline, calls


def test_overlapping_stream_rejected_before_second_source_registration(monkeypatch):
    pipeline, calls = subject(monkeypatch, lambda *a: iter(()))
    first = pipelines.IndexPipeline.stream(pipeline, "https://first", False)
    second = pipelines.IndexPipeline.stream(pipeline, "https://second", False)
    try:
        next(first)
        with pytest.raises(RuntimeError, match="active.*indexing"):
            next(second)
        assert calls == ["lookup", "source"]
    finally:
        first.close()
        second.close()


def test_stream_close_waits_for_producer_and_never_finishes(monkeypatch):
    entered, release, stopped, closed = (threading.Event() for _ in range(4))
    producer_threads = []
    writes = []

    def writer():
        producer_threads.append(threading.current_thread())
        entered.set()
        try:
            assert release.wait(5)
            writes.append("in-flight write")
            yield "batch"
            writes.append("later batch")
        finally:
            stopped.set()

    def handle(*args):
        artifacts.schedule_writer(pipeline, writer)
        yield Document("scheduled", channel="debug")

    pipeline, calls = subject(monkeypatch, handle)
    stream = pipelines.IndexPipeline.stream(pipeline, "https://first", False)
    for _ in range(3):
        next(stream)
    assert entered.wait(5)

    def close():
        try:
            stream.close()
        finally:
            closed.set()

    closer = threading.Thread(target=close)
    try:
        closer.start()
        assert pipeline._artifact_writer_future.stop_requested.wait(2)
        assert not closed.is_set()
        assert not stopped.is_set()
    finally:
        release.set()
        closer.join(5)
        for thread in producer_threads:
            thread.join(5)
            assert not thread.is_alive()
        assert not closer.is_alive()
    assert writes == ["in-flight write"]
    assert stopped.is_set() and closed.is_set()
    assert "finish" not in calls
