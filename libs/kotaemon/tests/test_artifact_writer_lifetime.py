import threading
from types import SimpleNamespace

import pytest

from kotaemon import artifact_pipeline as artifacts


@pytest.fixture
def blocked_writer():
    entered, release = threading.Event(), threading.Event()
    threads = []

    def produce():
        threads.append(threading.current_thread())
        entered.set()
        assert release.wait(5)
        yield "written"

    writer = artifacts.consume_in_background(produce)
    try:
        assert entered.wait(5)
        yield writer
    finally:
        release.set()
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()


def test_running_producer_cannot_be_cancelled_as_pending(blocked_writer):
    assert blocked_writer.running()
    assert blocked_writer.cancel() is False
    assert not blocked_writer.done()


@pytest.mark.parametrize("enabled", [False, True])
def test_new_generation_cannot_disown_live_writer(blocked_writer, enabled):
    subject = SimpleNamespace(
        _artifact_writer_future=blocked_writer, _artifact_generation="old"
    )
    metadata = {"file_id": "new"}
    with pytest.raises(RuntimeError, match="active.*writer"):
        artifacts.begin_indexing_artifacts(subject, metadata, enabled=enabled)
    assert subject._artifact_writer_future is blocked_writer
    assert subject._artifact_generation == "old"
    assert metadata == {"file_id": "new"}


def test_background_explicitly_closes_retained_iterator_after_failure():
    error = ValueError("write failed")

    class Writer:
        closed = False

        def __iter__(self):
            return self

        def __next__(self):
            raise error

        def close(self):
            self.closed = True

    iterator = Writer()
    threads = []

    def factory():
        threads.append(threading.current_thread())
        return iterator

    writer = artifacts.consume_in_background(factory)
    try:
        with pytest.raises(ValueError) as caught:
            writer.result(5)
        assert caught.value is error
        assert iterator.closed
    finally:
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()


def test_start_failure_completes_the_future_and_preserves_error(monkeypatch):
    failure = OSError("cannot start writer")
    results = []
    original = artifacts._ArtifactWriter.set_exception

    def observe(self, error):
        original(self, error)
        results.append(self)

    def fail(self):
        raise failure

    monkeypatch.setattr(artifacts._ArtifactWriter, "set_exception", observe)
    monkeypatch.setattr(threading.Thread, "start", fail)
    with pytest.raises(OSError) as caught:
        artifacts.consume_in_background(lambda: pytest.fail("must not run factory"))
    assert caught.value is failure
    assert len(results) == 1 and results[0].done()
    assert results[0].exception() is failure
    assert not results[0].thread.is_alive()


@pytest.mark.parametrize(
    "primary",
    [None, ValueError("primary"), KeyboardInterrupt("cancel"), GeneratorExit()],
)
def test_iterator_close_error_never_overwrites_primary(caplog, primary):
    class Iterator:
        def close(self):
            raise OSError("owned iterator close failed")

    with pytest.raises(type(primary) if primary is not None else OSError) as caught:
        with artifacts.owned_iterator(Iterator()):
            if primary is not None:
                raise primary
    if primary is not None:
        assert caught.value is primary
        assert "Indexing iterator cleanup failed" in caplog.text


def test_start_error_after_native_thread_started_joins_before_return(monkeypatch):
    entered, release, returned, recorded = (threading.Event() for _ in range(4))
    original = threading.Thread.start
    writers, errors = [], []
    failure = KeyboardInterrupt("startup interrupted")

    def interrupted_start(thread):
        original(thread)
        writer = getattr(thread._target, "__self__", None)
        if isinstance(writer, artifacts._ArtifactWriter):
            writers.append(writer)
            recorded.set()
            assert entered.wait(5)
            raise failure

    def produce():
        entered.set()
        assert release.wait(5)
        yield "partial"

    def call():
        try:
            artifacts.consume_in_background(produce)
        except KeyboardInterrupt as exc:
            errors.append(exc)
        finally:
            returned.set()

    monkeypatch.setattr(threading.Thread, "start", interrupted_start)
    caller = threading.Thread(target=call)
    try:
        caller.start()
        assert entered.wait(5)
        assert recorded.wait(5)
        assert writers[0].stop_requested.wait(2)
        assert not returned.is_set()
    finally:
        release.set()
        caller.join(5)
        for writer in writers:
            writer.thread.join(5)
            assert not writer.thread.is_alive()
        assert not caller.is_alive()
    assert errors == [failure]
