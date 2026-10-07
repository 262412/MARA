"""Own a FunctionAgent workflow until a chat stream is consumed or closed."""

import asyncio
from contextlib import suppress

from llama_index.core.agent.workflow.workflow_events import AgentStream, ToolCallResult
from llama_index.core.chat_engine.types import StreamingAgentChatResponse
from workflows.errors import WorkflowCancelledByUser


class OpenAIAgentStream(StreamingAgentChatResponse):
    def __init__(self, handler, owner, before):
        super().__init__(is_writing_to_memory=False)
        self.handler = handler
        self.owner = owner
        self.before = before
        self.sync_loop = None
        self.events = []
        self._failure_delivered = False

    async def async_response_gen(self):
        try:
            async for event in self.handler.stream_events():
                self.events.append(event)
                if isinstance(event, ToolCallResult):
                    self.sources.append(event.tool_output)
                elif (
                    isinstance(event, AgentStream)
                    and not event.tool_calls
                    and event.delta
                ):
                    self.unformatted_response += event.delta
                    yield event.delta
            result = await asyncio.shield(self.handler)
            self.response = str(result)
            self.set_source_nodes()
            self.is_done = True
            if not self.unformatted_response and self.response:
                yield self.response
        except BaseException:
            self._failure_delivered = True
            raise
        finally:
            await self.aclose()

    async def aclose(self):
        try:
            if not self.is_done:
                if not self.handler.done():
                    await self.handler.cancel_run()
                if self._failure_delivered and self.handler.done():
                    if not self.handler.cancelled():
                        self.handler.exception()
                else:
                    with suppress(WorkflowCancelledByUser, asyncio.CancelledError):
                        await asyncio.shield(self.handler)
        finally:
            if not self.is_done:
                self.owner.memory.set(self.before)
            self.owner._active = False

    @property
    def response_gen(self):
        if self.sync_loop is None:
            raise RuntimeError("Use async_response_gen for an async stream")
        generator = self.async_response_gen()
        try:
            while True:
                try:
                    yield self.sync_loop.run_until_complete(generator.__anext__())
                except StopAsyncIteration:
                    break
        finally:
            self.sync_loop.run_until_complete(generator.aclose())
            self.close()

    def close(self):
        if self.sync_loop is not None and not self.sync_loop.is_closed():
            try:
                self.sync_loop.run_until_complete(self.aclose())
                self.sync_loop.run_until_complete(self.sync_loop.shutdown_asyncgens())
            finally:
                self.sync_loop.close()
