"""Keep Windows stdio subprocess ownership off a caller's Selector loop."""

import asyncio
import logging
import sys
import threading
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


async def _close_loop_tasks(loop):
    pending = asyncio.all_tasks(loop) - {asyncio.current_task()}
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    await loop.shutdown_asyncgens()
    await loop.shutdown_default_executor()


class _StdioOperation:
    """One operation, one Proactor loop, and one joinable owner thread."""

    def __init__(self, operation: Callable[[], Coroutine[Any, Any, Any]]):
        self.operation = operation
        self.lock = threading.Lock()
        self.cancel_requested = False
        self.cancel_owner: Callable[[], Any] | None = None
        self.result: Any = None
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self.run, name="mara-mcp-stdio")

    def cancel(self):
        with self.lock:
            if not self.cancel_requested:
                self.cancel_requested = True
                if self.cancel_owner is not None:
                    self.cancel_owner()

    def run(self):
        loop = None
        try:
            loop = asyncio.ProactorEventLoop()
            owner = loop.create_task(self.operation())
            with self.lock:
                self.cancel_owner = lambda: loop.call_soon_threadsafe(owner.cancel)
                if self.cancel_requested:
                    owner.cancel()
            self.result = loop.run_until_complete(owner)
        except BaseException as exc:
            logger.debug("MCP stdio owner propagates %s to caller", type(exc).__name__)
            self.error = exc
        finally:
            with self.lock:
                self.cancel_owner = None
            if loop is not None:
                self.close(loop)

    def close(self, loop):
        try:
            loop.run_until_complete(_close_loop_tasks(loop))
        except BaseException as exc:
            if self.error is None:
                self.error = exc
            else:
                logger.error("MCP loop cleanup failed: %s", type(exc).__name__)
        finally:
            loop.close()


async def run_mcp_operation(transport, operation):
    """Run the complete operation once, and finish ownership before cancelling.

    Only Windows stdio on a Selector caller needs a worker. The factory creates
    the coroutine inside that worker; SDK contexts never cross tasks or loops.
    """
    if not (
        sys.platform == "win32"
        and transport == "stdio"
        and isinstance(asyncio.get_running_loop(), asyncio.SelectorEventLoop)
    ):
        return await operation()

    worker = _StdioOperation(operation)
    worker.thread.start()
    joined = asyncio.create_task(asyncio.to_thread(worker.thread.join))
    cancellation = None
    while True:
        try:
            await asyncio.shield(joined)
            break
        except asyncio.CancelledError as exc:
            if cancellation is None:
                cancellation = exc
                worker.cancel()
    if cancellation is not None:
        if worker.error is not None and not isinstance(
            worker.error, asyncio.CancelledError
        ):
            logger.error(
                "MCP cancellation cleanup failed: %s", type(worker.error).__name__
            )
        raise cancellation
    if worker.error is not None:
        raise worker.error
    return worker.result
