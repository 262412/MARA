"""Deterministic ownership tests; live Windows SDK coverage lives separately."""

import asyncio
import sys
import threading
from types import SimpleNamespace

import pytest

from kotaemon.agents.tools import mcp_operation


@pytest.fixture
def worker_path(monkeypatch):
    # Exercise the bridge mechanics on Linux too, without changing loop policy.
    monkeypatch.setattr(mcp_operation, "sys", SimpleNamespace(platform="win32"))
    if sys.platform != "win32":
        monkeypatch.setattr(
            asyncio, "ProactorEventLoop", asyncio.SelectorEventLoop, raising=False
        )


def run_selector(operation):
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(operation())
    finally:
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()


async def reached(event):
    assert await asyncio.to_thread(event.wait, 5), "Worker did not reach its barrier"


def test_worker_preserves_single_business_exception(worker_path):
    failure = RuntimeError("single owned failure")
    calls = []

    async def operation():
        calls.append(threading.current_thread())
        raise failure

    async def exercise():
        with pytest.raises(RuntimeError) as caught:
            await mcp_operation.run_mcp_operation("stdio", operation)
        assert caught.value is failure

    run_selector(exercise)
    assert len(calls) == 1 and not calls[0].is_alive()


def test_repeated_cancel_waits_for_same_task_cleanup(worker_path):
    entered, cleaning, release = (threading.Event() for _ in range(3))
    owners = []

    async def operation():
        owners.append((threading.current_thread(), asyncio.current_task()))
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await asyncio.to_thread(release.wait, 5)
            assert release.is_set()
            owners.append((threading.current_thread(), asyncio.current_task()))

    async def exercise():
        task = asyncio.create_task(mcp_operation.run_mcp_operation("stdio", operation))
        try:
            await reached(entered)
            task.cancel("first")
            await reached(cleaning)
            task.cancel("second")
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)

    run_selector(exercise)
    assert len(owners) == 2 and owners[0] == owners[1]
    assert not owners[0][0].is_alive()


def test_cancel_before_owner_registration(worker_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = mcp_operation._StdioOperation.run
    calls = []
    threads = []

    def delayed(worker):
        threads.append(threading.current_thread())
        entered.set()
        assert release.wait(5)
        original(worker)

    monkeypatch.setattr(mcp_operation._StdioOperation, "run", delayed)

    async def operation():
        calls.append("must not execute")

    async def exercise():
        task = asyncio.create_task(mcp_operation.run_mcp_operation("stdio", operation))
        try:
            await reached(entered)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)

    run_selector(exercise)
    assert not calls and len(threads) == 1 and not threads[0].is_alive()


@pytest.mark.parametrize("transport", ["sse", "stdio"])
def test_supported_loop_keeps_operation_in_caller(transport, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Supported caller unexpectedly migrated to a worker")

    monkeypatch.setattr(mcp_operation, "_StdioOperation", forbidden)

    async def exercise():
        owner = asyncio.current_task()

        async def operation():
            assert asyncio.current_task() is owner
            return "local result"

        assert (
            await mcp_operation.run_mcp_operation(transport, operation)
            == "local result"
        )

    loop = (
        getattr(asyncio, "ProactorEventLoop")()
        if sys.platform == "win32"
        else asyncio.SelectorEventLoop()
    )
    try:
        loop.run_until_complete(exercise())
    finally:
        loop.close()


def test_worker_loop_creation_error_is_single_and_joined(worker_path, monkeypatch):
    failure = RuntimeError("loop creation failed")
    threads = []

    def fail():
        threads.append(threading.current_thread())
        raise failure

    monkeypatch.setattr(asyncio, "ProactorEventLoop", fail)

    async def operation():
        raise AssertionError("Operation must not start without its loop")

    async def exercise():
        with pytest.raises(RuntimeError) as caught:
            await mcp_operation.run_mcp_operation("stdio", operation)
        assert caught.value is failure

    run_selector(exercise)
    assert len(threads) == 1 and not threads[0].is_alive()


@pytest.mark.parametrize("business_failure", [False, True])
def test_loop_cleanup_error_preserves_primary(
    worker_path, monkeypatch, business_failure
):
    primary = RuntimeError("business failure")
    secondary = ValueError("shutdown failure")
    factory = getattr(asyncio, "ProactorEventLoop")

    def loop_factory():
        loop = factory()

        async def fail():
            raise secondary

        monkeypatch.setattr(loop, "shutdown_asyncgens", fail)
        return loop

    monkeypatch.setattr(asyncio, "ProactorEventLoop", loop_factory)

    async def operation():
        if business_failure:
            raise primary
        return "result"

    async def exercise():
        with pytest.raises((ValueError, RuntimeError)) as caught:
            await mcp_operation.run_mcp_operation("stdio", operation)
        assert caught.value is (primary if business_failure else secondary)

    run_selector(exercise)


def test_owned_background_task_finishes_before_result(worker_path):
    cleaned = threading.Event()

    async def background():
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    async def operation():
        asyncio.create_task(background())
        await asyncio.sleep(0)
        return "owned result"

    async def exercise():
        assert (
            await mcp_operation.run_mcp_operation("stdio", operation) == "owned result"
        )
        assert cleaned.is_set()

    run_selector(exercise)


def test_cancellation_remains_primary_after_cleanup_error(worker_path, caplog):
    entered = threading.Event()

    async def operation():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            raise ValueError("private payload must not be logged")

    async def exercise():
        task = asyncio.create_task(mcp_operation.run_mcp_operation("stdio", operation))
        await reached(entered)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run_selector(exercise)
    assert "MCP cancellation cleanup failed: ValueError" in caplog.text
    assert "private payload" not in caplog.text


@pytest.mark.parametrize("business_failure", [False, True])
def test_final_loop_close_error_is_not_lost(worker_path, monkeypatch, business_failure):
    primary = RuntimeError("business failure")
    secondary = ValueError("loop close failure")
    factory = getattr(asyncio, "ProactorEventLoop")

    def loop_factory():
        loop = factory()
        original_close = loop.close

        def fail():
            original_close()
            raise secondary

        monkeypatch.setattr(loop, "close", fail)
        return loop

    monkeypatch.setattr(asyncio, "ProactorEventLoop", loop_factory)

    async def operation():
        if business_failure:
            raise primary
        return "must not mask close failure"

    async def exercise():
        with pytest.raises((ValueError, RuntimeError)) as caught:
            await mcp_operation.run_mcp_operation("stdio", operation)
        assert caught.value is (primary if business_failure else secondary)

    run_selector(exercise)
