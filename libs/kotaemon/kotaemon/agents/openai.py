"""First-party migration of the old OpenAIAgent chat interface.

The official FunctionAgent owns planning and tool dispatch. This adapter retains
the old chat response, memory, callback, and inclusive function-call limit seams.
It does not provide the removed third-party Python import or AgentRunner task API.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from llama_index.core import Settings
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.agent.workflow.workflow_events import AgentStream
from llama_index.core.base.llms.types import ToolCallBlock
from llama_index.core.callbacks import CBEventType, EventPayload
from llama_index.core.chat_engine.types import AgentChatResponse
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import ToolOutput
from llama_index.llms.openai import OpenAI
from pydantic import Field, PrivateAttr
from workflows.errors import WorkflowRuntimeError

from .openai_stream import OpenAIAgentStream


def _require_sync_context(alternative):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError(
        f"Synchronous Agent entry cannot run inside an active event loop; use await {alternative}"
    )


class _ChatFunctionAgent(FunctionAgent):
    max_function_calls: int = 5
    function_calls: int = 0
    prefix_messages: list[ChatMessage] = Field(default_factory=list)
    synchronous: bool = False
    tool_call_parser: Callable | None = None
    _original_message: ChatMessage | None = PrivateAttr(default=None)

    def _parsed_response(self, response):
        assert self.tool_call_parser is not None
        self._original_message = response.message
        calls = []
        parsed_arguments = {}
        for original in response.message.additional_kwargs.get("tool_calls", []):
            call = original.model_copy(deep=True)
            arguments = self.tool_call_parser(original)
            parsed_arguments[call.id] = arguments
            call.function.arguments = json.dumps(arguments)
            calls.append(call)
        blocks = []
        for block in response.message.blocks:
            if isinstance(block, ToolCallBlock):
                block = block.model_copy(
                    update={"tool_kwargs": parsed_arguments[block.tool_call_id]}
                )
            blocks.append(block)
        message = response.message.model_copy(
            update={
                "blocks": blocks,
                "additional_kwargs": {
                    **response.message.additional_kwargs,
                    "tool_calls": calls,
                },
            }
        )
        return response.model_copy(update={"message": message})

    async def _get_response(self, current_llm_input, tools):
        if self.synchronous:
            response = self.llm.chat_with_tools(
                **self._chat_kwargs(current_llm_input, tools)
            )
        else:
            response = await super()._get_response(current_llm_input, tools)
        return self._parsed_response(response) if self.tool_call_parser else response

    def _chat_kwargs(self, current_llm_input, tools):
        kwargs = {
            "chat_history": current_llm_input,
            "tools": tools,
            "allow_parallel_tool_calls": False,
        }
        if (
            self.initial_tool_choice is not None
            and current_llm_input[-1].role == "user"
        ):
            kwargs["tool_choice"] = self.initial_tool_choice
        return kwargs

    async def _get_streaming_response(self, ctx, current_llm_input, tools):
        if not self.synchronous and self.tool_call_parser is None:
            return await super()._get_streaming_response(ctx, current_llm_input, tools)
        kwargs = self._chat_kwargs(current_llm_input, tools)
        if self.synchronous:
            stream = self._sync_chunks(self.llm.stream_chat_with_tools(**kwargs))
        else:
            stream = await self.llm.astream_chat_with_tools(**kwargs)
        response = None
        async for response in stream:
            calls = response.message.additional_kwargs.get("tool_calls", [])
            ctx.write_event_to_stream(
                AgentStream(
                    delta="" if calls else response.delta or "",
                    response=response.message.content or "",
                    tool_calls=[],
                    raw=response.raw,
                    current_agent_name=self.name,
                )
            )
        if response is None:
            raise ValueError("Empty OpenAI chat stream")
        return self._parsed_response(response) if self.tool_call_parser else response

    async def _sync_chunks(self, stream):
        try:
            for response in stream:
                yield response
        finally:
            stream.close()

    async def take_step(self, ctx, llm_input, tools, memory):
        result = await super().take_step(
            ctx, [*self.prefix_messages, *llm_input], tools, memory
        )
        if self._original_message is not None:
            result.response = self._original_message
            scratchpad = await ctx.store.get(self.scratchpad_key, default=[])
            scratchpad[-1] = self._original_message
            await ctx.store.set(self.scratchpad_key, scratchpad)
        # Preserve the verified old worker's inclusive limit, including the
        # final model response after the last permitted tool batch.
        if self.function_calls > self.max_function_calls:
            result.tool_calls = []
        self.function_calls += len(result.tool_calls)
        return result

    async def _call_tool(self, ctx, tool, tool_input):
        # The old sync worker reports exceptions as observations, while its
        # async worker propagates them. Preserve that verified distinction.
        with self.llm.callback_manager.event(
            CBEventType.FUNCTION_CALL,
            payload={
                EventPayload.FUNCTION_CALL: tool_input,
                EventPayload.TOOL: tool.metadata,
            },
        ) as event:
            try:
                output = (
                    tool.call(**tool_input)
                    if self.synchronous
                    else await tool.acall(**tool_input)
                )
            except Exception as exc:
                if not self.synchronous:
                    raise
                output = ToolOutput(
                    content=f"Error: {exc}",
                    tool_name=tool.metadata.name,
                    raw_input={"kwargs": tool_input},
                    raw_output=exc,
                )
            event.on_end(payload={EventPayload.FUNCTION_OUTPUT: str(output)})
            return output


class OpenAIAgent:
    """Chat-method adapter; advanced AgentRunner task APIs require migration."""

    def __init__(
        self,
        tools,
        llm,
        memory,
        prefix_messages,
        verbose=False,
        max_function_calls=5,
        default_tool_choice="auto",
        callback_manager=None,
        tool_retriever=None,
        tool_call_parser=None,
    ):
        if not isinstance(llm, OpenAI) or not llm.metadata.is_function_calling_model:
            raise ValueError("llm must be a function-calling OpenAI instance")
        self.llm = llm
        self.memory = memory
        self.callback_manager = callback_manager or llm.callback_manager
        self.llm.callback_manager = self.callback_manager
        self.default_tool_choice = default_tool_choice
        self._settings = dict(
            tools=tools,
            llm=llm,
            prefix_messages=prefix_messages,
            verbose=verbose,
            max_function_calls=max_function_calls,
            tool_retriever=tool_retriever,
            tool_call_parser=tool_call_parser,
        )
        self._active = False

    @classmethod
    def from_tools(
        cls,
        tools=None,
        tool_retriever=None,
        llm=None,
        chat_history=None,
        memory=None,
        memory_cls=ChatMemoryBuffer,
        verbose=False,
        max_function_calls=5,
        default_tool_choice="auto",
        callback_manager=None,
        system_prompt=None,
        prefix_messages=None,
        tool_call_parser=None,
        **kwargs: Any,
    ):
        llm = llm or Settings.llm
        if system_prompt is not None:
            if prefix_messages is not None:
                raise ValueError(
                    "Cannot specify both system_prompt and prefix_messages"
                )
            prefix_messages = [ChatMessage(content=system_prompt, role="system")]
        return cls(
            tools=tools or [],
            llm=llm,
            memory=memory or memory_cls.from_defaults(chat_history or [], llm=llm),
            prefix_messages=prefix_messages or [],
            verbose=verbose,
            max_function_calls=max_function_calls,
            default_tool_choice=default_tool_choice,
            callback_manager=callback_manager,
            tool_retriever=tool_retriever,
            tool_call_parser=tool_call_parser,
        )

    @property
    def chat_history(self):
        return self.memory.get_all()

    def reset(self):
        if self._active:
            raise RuntimeError("Close or cancel the active chat before reset")
        self.memory.reset()

    def _start(self, message, chat_history, tool_choice, *, streaming, synchronous):
        if self._active:
            raise RuntimeError("A chat is already active on this agent")
        choice = self.default_tool_choice if tool_choice is None else tool_choice
        if isinstance(choice, dict):
            choice = choice["function"]["name"]
        agent = _ChatFunctionAgent(
            **self._settings,
            initial_tool_choice=choice,
            streaming=streaming,
            allow_parallel_tool_calls=False,
            synchronous=synchronous,
        )
        before = self.memory.get_all()
        handler = agent.run(
            user_msg=message,
            chat_history=chat_history,
            memory=self.memory,
            max_iterations=max(3, self._settings["max_function_calls"] + 3),
        )
        self._active = True
        return OpenAIAgentStream(handler, self, before)

    async def _chat_response(self, message, chat_history, tool_choice, *, synchronous):
        with self.callback_manager.event(
            CBEventType.AGENT_STEP,
            payload={EventPayload.MESSAGES: [message]},
        ) as event:
            stream = self._start(
                message,
                chat_history,
                tool_choice,
                streaming=False,
                synchronous=synchronous,
            )
            try:
                async for _ in stream.async_response_gen():
                    pass
                response = AgentChatResponse(
                    response=stream.response, sources=stream.sources
                )
                event.on_end(payload={EventPayload.RESPONSE: response})
                return response
            except WorkflowRuntimeError as exc:
                if exc.__cause__ is not None:
                    raise exc.__cause__ from exc
                raise

    def chat(self, message, chat_history=None, tool_choice=None):
        _require_sync_context("achat")
        return asyncio.run(
            self._chat_response(message, chat_history, tool_choice, synchronous=True)
        )

    async def astream_chat(self, message, chat_history=None, tool_choice=None):
        return await self._stream_response(
            message, chat_history, tool_choice, synchronous=False
        )

    async def achat(self, message, chat_history=None, tool_choice=None):
        return await self._chat_response(
            message, chat_history, tool_choice, synchronous=False
        )

    async def _stream_response(
        self, message, chat_history, tool_choice, *, synchronous
    ):
        with self.callback_manager.event(
            CBEventType.AGENT_STEP,
            payload={EventPayload.MESSAGES: [message]},
        ) as event:
            response = self._start(
                message,
                chat_history,
                tool_choice,
                streaming=True,
                synchronous=synchronous,
            )
            event.on_end(payload={EventPayload.RESPONSE: response})
            return response

    def stream_chat(self, message, chat_history=None, tool_choice=None):
        _require_sync_context("astream_chat")
        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(
                self._stream_response(
                    message, chat_history, tool_choice, synchronous=True
                )
            )
        except BaseException:
            loop.close()
            raise
        response.sync_loop = loop
        return response
