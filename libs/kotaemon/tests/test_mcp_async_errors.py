"""Business exceptions must propagate without retrying an external invocation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from kotaemon.agents.tools.mcp import _run_async


@pytest.mark.parametrize(
    "context", ["no_loop", "idle_loop", "closed_loop", "running_loop", "worker"]
)
@pytest.mark.parametrize("fails", [False, True])
def test_sync_bridge_invokes_once_and_preserves_business_error(context, fails):
    calls = []
    failure = RuntimeError("owned business failure")

    async def operation():
        calls.append("external effect")
        if fails:
            raise failure
        return "done"

    def invoke():
        if fails:
            with pytest.raises(RuntimeError) as caught:
                _run_async(operation())
            assert caught.value is failure
        else:
            assert _run_async(operation()) == "done"

    async def inside_loop():
        invoke()

    asyncio.set_event_loop(None)
    if context in {"idle_loop", "closed_loop"}:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if context == "closed_loop":
            loop.close()
        try:
            invoke()
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    elif context == "running_loop":
        asyncio.run(inside_loop())
    elif context == "worker":
        with ThreadPoolExecutor() as pool:
            pool.submit(invoke).result()
    else:
        invoke()
    assert calls == ["external effect"]
