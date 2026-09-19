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
