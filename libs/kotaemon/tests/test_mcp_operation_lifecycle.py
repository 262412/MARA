"""Complete MCP operations must own cancellation, contexts and worker exit."""

import asyncio
import json
import sys
import threading
from contextlib import asynccontextmanager

import psutil
import pytest

from kotaemon.agents.tools import mcp

from . import test_mcp_live_sessions as fixtures
from .test_mcp_live_sessions import records, stop_owned_held_server, until

owned_server = fixtures.owned_server


def execution_identity():
    return (
        threading.current_thread(),
        asyncio.get_running_loop(),
        asyncio.current_task(),
    )


def test_explicit_selector_cancellation_finishes_owned_operation(
    owned_server, monkeypatch
):
    config, evidence = owned_server
    original = mcp.initialized_session
    ownership = []

    @asynccontextmanager
    async def observed(*args):
        identity = execution_identity()
        ownership.append(("enter", identity))
        try:
            async with original(*args) as session:
                yield session
        finally:
            ownership.append(("exit", execution_identity()))

    monkeypatch.setattr(mcp, "initialized_session", observed)
    policy = asyncio.get_event_loop_policy()
    loop = asyncio.SelectorEventLoop()
    watchdog_events: list[dict[str, object]] = []
    watchdog = threading.Timer(
        10, stop_owned_held_server, args=(evidence, watchdog_events)
    )

    async def exercise():
        tool = mcp.create_tools_from_config(config)[0]
        task = asyncio.create_task(tool._arun_tool(value="hold"))
        try:
            await asyncio.to_thread(
                until, lambda: any(r["event"] == "held" for r in records(evidence))
            )
        finally:
            watchdog.start()
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        if config["transport"] == "stdio":
            assert all(not psutil.pid_exists(r["pid"]) for r in records(evidence))
        assert json.loads(await tool._arun_tool(value="after")) == {"value": "after"}
        assert asyncio.get_running_loop() is loop

    try:
        loop.run_until_complete(exercise())
    finally:
        watchdog.cancel()
        if watchdog.ident is not None:
            watchdog.join(timeout=10)
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
    assert not watchdog.is_alive()
    assert not watchdog_events, f"Watchdog rescue is failure: {watchdog_events}"
    assert asyncio.get_event_loop_policy() is policy
    assert len(ownership) == 6
    for enter, leave in zip(ownership[::2], ownership[1::2]):
        assert enter[0] == "enter" and leave == ("exit", enter[1])
        thread, operation_loop, _ = enter[1]
        if sys.platform == "win32" and config["transport"] == "stdio":
            assert isinstance(operation_loop, asyncio.ProactorEventLoop)
            assert thread is not threading.current_thread() and not thread.is_alive()
    print(
        json.dumps(
            {
                "policy": type(policy).__name__,
                "watchdog": watchdog_events,
                "contexts_completed": len(ownership) // 2,
            }
        )
    )
