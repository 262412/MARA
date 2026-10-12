"""Real LangChain model validation and SDK transport; no remote service calls."""

import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import BaseModel, Field

from kotaemon.base import AIMessage, HumanMessage, LLMInterface, SystemMessage
from kotaemon.llms.chats.base import ChatLLM
from kotaemon.llms.chats.langchain_based import LCChatMixin, LCChatOpenAI
from kotaemon.llms.chats.openai import ChatOpenAI, StructuredOutputChatOpenAI


class Lookup(BaseModel):
    """Look up a synthetic value."""

    query: str
    limit: int = 3


def completion():
    return {
        "id": "provider-id",
        "object": "chat.completion",
        "created": 1,
        "model": "synthetic",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "answer",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "Lookup",
                                "arguments": '{"query":"value"}',
                            },
                        }
                    ],
                },
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
    }


def chunks():
    for index, content in enumerate(("one", "two")):
        yield {
            "id": "provider-stream",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "synthetic",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content}
                    if index == 0
                    else {"content": content},
                    "finish_reason": None,
                }
            ],
        }
    yield {
        "id": "provider-stream",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "synthetic",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


@pytest.fixture
def transport():
    requests = []

    def respond(request):
        data = json.loads(request.content)
        requests.append(data)
        if data.get("stream"):
            body = (
                "".join("data: " + json.dumps(item) + "\n\n" for item in chunks())
                + "data: [DONE]\n\n"
            )
            return httpx.Response(
                200, text=body, headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json=completion())

    client = httpx.Client(transport=httpx.MockTransport(respond))
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    yield client, async_client, requests
    client.close()
    asyncio.run(async_client.aclose())


def model(transport):
    client, async_client, _ = transport
    return LCChatOpenAI(
        openai_api_key="synthetic-key",
        openai_api_base="https://example.invalid/v1",
        model="synthetic",
        temperature=0,
        max_retries=0,
        http_client=client,
        http_async_client=async_client,
    )


def history():
    return [
        SystemMessage(
            "system", doc_id="internal-system", metadata={"path": "private.pdf"}
        ),
        HumanMessage(
            content=[
                {"type": "text", "text": "question"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.invalid/image.png"},
                },
            ],
            doc_id="internal-human",
            id="user-id",
            name="user",
            metadata={"retrieval": "secret"},
        ),
        AIMessage("previous", id="previous-id"),
    ]


@pytest.mark.parametrize("method", ["invoke", "ainvoke"])
def test_real_chatopenai_round_trip_and_callback_validation(transport, method):
    wrapper = model(transport)
    values = history()
    before = [deepcopy(value.to_dict()) for value in values]
    callback = Events()
    if method == "invoke":
        output = wrapper.invoke(values, callbacks=[callback], stop=["end"])
    else:
        output = asyncio.run(
            wrapper.ainvoke(values, callbacks=[callback], stop=["end"])
        )
    assert isinstance(output, LLMInterface) and isinstance(
        output.messages[0], AIMessage
    )
    assert output.content == "answer"
    # This pinned integration drops the HTTP completion ID and supplies a run ID.
    # Compare with its actual native message, not a fabricated provider identity.
    assert output.messages[0].id == callback.message_ids[0]
    assert output.messages[0].doc_id != output.messages[0].id
    assert (
        output.total_tokens == 7
        and output.prompt_tokens == 3
        and output.completion_tokens == 4
    )
    assert output.tool_calls[0]["id"] == "call-1"
    assert output.messages[0].response_metadata["finish_reason"] == "tool_calls"
    assert len(transport[2]) == 1
    request = transport[2][0]
    assert [m["role"] for m in request["messages"]] == ["system", "user", "assistant"]
    assert request["messages"][1]["content"] == values[1].content
    assert request["stop"] == ["end"]
    assert "private.pdf" not in json.dumps(
        request
    ) and "internal-human" not in json.dumps(request)
    assert [value.to_dict() for value in values] == before
    assert callback.started == 1 and callback.ended == 1


@pytest.mark.parametrize("method", ["invoke", "ainvoke"])
def test_real_bind_tools_schema_and_arguments(transport, method):
    wrapper = model(transport)
    options = {"tools_pydantic": [Lookup], "tool_choice": "auto"}
    callback = Events()
    output = (
        wrapper.invoke("question", callbacks=[callback], **options)
        if method == "invoke"
        else asyncio.run(wrapper.ainvoke("question", callbacks=[callback], **options))
    )
    assert output.tool_calls[0]["args"] == {"query": "value"}
    assert output.messages[0].id == callback.message_ids[0]
    assert output.messages[0].response_metadata["id"] == "provider-id"
    assert output.messages[0].doc_id != output.messages[0].id
    assert output.total_tokens == 7
    assert len(transport[2]) == 1
    payload = transport[2][0]
    assert payload["tools"][0]["function"]["parameters"]["required"] == ["query"]
    assert (
        payload["tools"][0]["function"]["parameters"]["properties"]["limit"]["default"]
        == 3
    )
    assert payload["tool_choice"] == "auto"
    assert options == {"tools_pydantic": [Lookup], "tool_choice": "auto"}


@pytest.mark.parametrize("method", ["stream", "astream"])
def test_real_stream_input_output_ids_order_usage(transport, method):
    wrapper = model(transport)
    values = history()
    callback = Events()

    async def collect():
        return [
            item
            async for item in wrapper.astream(values, config={"callbacks": [callback]})
        ]

    output = (
        list(wrapper.stream(values, config={"callbacks": [callback]}))
        if method == "stream"
        else asyncio.run(collect())
    )
    assert "".join(item.content for item in output) == "onetwo"
    assert all(isinstance(item, LLMInterface) for item in output)
    assert [item.messages[0].id for item in output] == callback.chunk_ids
    assert all(item.messages[0].doc_id != item.messages[0].id for item in output)
    assert sum(item.total_tokens for item in output) == 5
    assert output[-1].messages[0].chunk_position == "last"
    assert len(transport[2]) == 1
    assert transport[2][0]["messages"][1]["content"] == values[1].content
    assert "private.pdf" not in json.dumps(transport[2][0])


class Events(BaseCallbackHandler):
    def __init__(self):
        self.started = 0
        self.ended = 0
        self.errors = 0
        self.message_ids = []
        self.chunk_ids = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        from langchain_core.messages import BaseMessage

        assert all(isinstance(m, BaseMessage) for row in messages for m in row)
        self.started += 1

    def on_llm_end(self, response, **kwargs):
        self.ended += 1
        self.message_ids = [
            gen.message.id for row in response.generations for gen in row
        ]

    def on_llm_new_token(self, token, chunk=None, **kwargs):
        self.chunk_ids.append(chunk.message.id)

    def on_llm_error(self, error, **kwargs):
        self.errors += 1


class StreamModel(BaseChatModel):
    closed_sync: int = 0
    closed_async: int = 0
    calls: list = Field(default_factory=list)
    failure: bool = False
    block: bool = False

    @property
    def _llm_type(self):
        return "s14d-real-validation"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        if self.failure:
            raise RuntimeError("synthetic provider failure")
        return ChatResult(
            generations=[ChatGeneration(message=LCAIMessage(content="answer"))]
        )

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        try:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="first", id="provider")
            )
            if self.failure:
                raise RuntimeError("synthetic provider failure")
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="second", id="provider")
            )
        finally:
            self.closed_sync += 1

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        try:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="first", id="provider")
            )
            if self.block:
                await asyncio.Event().wait()
            if self.failure:
                raise RuntimeError("synthetic provider failure")
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="second", id="provider")
            )
        finally:
            self.closed_async += 1


class ControlledChat(LCChatMixin, ChatLLM):
    def _get_lc_class(self):
        return StreamModel


def test_stream_early_close_and_exception_do_not_repeat_calls():
    wrapper = ControlledChat()
    stream = wrapper.stream(HumanMessage("question"))
    assert next(stream).content == "first"
    stream.close()
    assert wrapper._obj.closed_sync == 1 and len(wrapper._obj.calls) == 1
    failure = ControlledChat(failure=True)
    stream = failure.stream("question")
    assert next(stream).content == "first"
    with pytest.raises(RuntimeError, match="synthetic provider failure"):
        next(stream)
    assert failure._obj.closed_sync == 1 and len(failure._obj.calls) == 1


def test_async_cancel_close_and_exception_do_not_repeat_calls():
    async def check():
        wrapper = ControlledChat(block=True)
        stream = wrapper.astream("question")
        assert (await anext(stream)).content == "first"
        task = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await stream.aclose()
        assert wrapper._obj.closed_async == 1 and len(wrapper._obj.calls) == 1
        failure = ControlledChat(failure=True)
        stream = failure.astream("question")
        await anext(stream)
        with pytest.raises(RuntimeError, match="synthetic provider failure"):
            await anext(stream)
        assert failure._obj.closed_async == 1 and len(failure._obj.calls) == 1

    asyncio.run(check())


def test_direct_native_consumer_preserves_identity_and_rejects_invalid_payload():
    wrapper = ControlledChat()
    message = HumanMessage("direct")
    assert wrapper._obj.invoke([message]).content == "answer"
    assert wrapper._obj.calls == [[message]]
    with pytest.raises((ValueError, TypeError)):
        wrapper.invoke(AIMessage(object()))
    assert wrapper._obj.calls == [[message]]


def test_direct_openai_payload_output_and_structured_contract_are_unchanged():
    wrapper = ChatOpenAI(api_key="synthetic", model="synthetic")
    values = history()
    assert wrapper.prepare_message(values) == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": values[1].content},
        {"role": "assistant", "content": "previous"},
    ]
    response = completion()
    before = deepcopy(response)
    output = wrapper.prepare_output(response)
    assert output.candidates == ["answer"] and output.total_tokens == 7
    assert (
        output.additional_kwargs["tool_calls"]
        == response["choices"][0]["message"]["tool_calls"]
    )
    assert output.messages[0].id is None
    assert response == before
    structured = StructuredOutputChatOpenAI(
        api_key="synthetic", model="synthetic", response_schema=Lookup
    )
    response["choices"][0]["message"]["parsed"] = {"query": "answer", "limit": 3}
    result = structured.prepare_output(response)
    assert result.parsed == {"query": "answer", "limit": 3} and result.refusal == ""
