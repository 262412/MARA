"""Old OpenAIAgent public methods exercised through a synthetic SDK transport."""

import asyncio
import json
from typing import Any

import httpx
import pytest
from llama_index.agent.openai import OpenAIAgent
from llama_index.core.callbacks import CallbackManager, CBEventType, LlamaDebugHandler
from llama_index.core.chat_engine.types import (
    AgentChatResponse,
    StreamingAgentChatResponse,
)
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI


def _agent_response(request, requests, controls):
    data = json.loads(request.content)
    requests.append(data)
    use_tool = controls["repeat"] or not any(
        m["role"] == "tool" for m in data["messages"]
    )
    call = {
        "id": "call-" + str(len(requests)),
        "type": "function",
        "function": {
            "name": "add",
            "arguments": controls.get("arguments", '{"a":2,"b":3}'),
        },
    }
    message = (
        {"role": "assistant", "content": None, "tool_calls": [call]}
        if use_tool
        else {"role": "assistant", "content": "answer 5"}
    )
    base = {"id": "completion-fixture", "created": 1, "model": "gpt-4o-mini"}
    if data.get("stream"):
        deltas = (
            [{"role": "assistant", "tool_calls": [{"index": 0, **call}]}]
            if use_tool
            else [{"role": "assistant", "content": "answer"}, {"content": " 5"}]
        )
        chunks = [
            {
                **base,
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            for delta in deltas
        ]
        chunks.append(
            {
                **base,
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if use_tool else "stop",
                    }
                ],
            }
        )
        return httpx.Response(
            200,
            text="".join("data: " + json.dumps(item) + "\n\n" for item in chunks)
            + "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )
    return httpx.Response(
        200,
        json={
            **base,
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if use_tool else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            },
        },
    )


@pytest.fixture
def agent_runtime():
    requests: list[dict[str, Any]] = []
    calls: list[tuple[int, int]] = []
    controls: dict[str, Any] = {"repeat": False, "error": False}

    def add(a: int, b: int) -> int:
        """Add two fixture integers."""
        calls.append((a, b))
        if controls["error"]:
            raise ValueError("synthetic tool failure")
        return a + b

    def respond(request):
        return _agent_response(request, requests, controls)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    debug = LlamaDebugHandler(print_trace_on_end=False)
    manager = CallbackManager([debug])
    llm = OpenAI(
        model="gpt-4o-mini",
        api_key="synthetic-key",
        api_base="https://example.invalid/v1",
        max_retries=0,
        http_client=client,
        async_http_client=async_client,
        callback_manager=manager,
    )

    async def async_add(a: int, b: int) -> int:
        if controls.get("pause"):
            controls["started"].set()
            try:
                await controls["release"].wait()
            finally:
                controls["closed"].set()
        return add(a, b)

    tool = FunctionTool.from_defaults(fn=add, async_fn=async_add)

    def create(**kwargs):
        memory = ChatMemoryBuffer.from_defaults(
            token_limit=10000, tokenizer_fn=lambda text: list(text)
        )
        return OpenAIAgent.from_tools(
            tools=[tool], llm=llm, memory=memory, callback_manager=manager, **kwargs
        )

    yield create, requests, calls, controls, debug
    client.close()
    asyncio.run(async_client.aclose())


@pytest.mark.parametrize("method", ["chat", "achat", "stream_chat", "astream_chat"])
def test_old_agent_methods_execute_tools_history_and_reset(agent_runtime, method):
    create, requests, calls, _, debug = agent_runtime
    agent = create(system_prompt="Fixture system")

    async def asynchronous():
        response = await getattr(agent, method)("add", tool_choice="add")
        if method == "astream_chat":
            return response, "".join(
                [token async for token in response.async_response_gen()]
            )
        return response, str(response)

    if method.startswith("a"):
        response, text = asyncio.run(asynchronous())
    else:
        response = getattr(agent, method)("add", tool_choice="add")
        text = (
            "".join(response.response_gen) if method == "stream_chat" else str(response)
        )
    assert isinstance(
        response,
        StreamingAgentChatResponse if "stream" in method else AgentChatResponse,
    )
    assert text == "answer 5"
    assert calls == [(2, 3)]
    assert len(requests) == 2
    assert requests[0]["tools"][0]["function"]["name"] == "add"
    assert requests[0]["tool_choice"]["function"]["name"] == "add"
    assert requests[0]["messages"][0] == {"role": "system", "content": "Fixture system"}
    tool_message = next(m for m in requests[1]["messages"] if m["role"] == "tool")
    assert tool_message["content"] == "5" and tool_message["tool_call_id"] == "call-1"
    assert response.sources[0].tool_name == "add"
    assert response.sources[0].raw_output == 5
    assert [str(m.role.value) for m in agent.chat_history] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert agent.chat_history[-1].content == "answer 5"
    assert debug.get_events(CBEventType.LLM)
    assert debug.get_events(CBEventType.FUNCTION_CALL)
    agent.reset()
    assert agent.chat_history == []


@pytest.mark.parametrize("method", ["chat", "achat"])
def test_old_agent_explicit_history_replaces_memory(agent_runtime, method):
    create, requests, _, _, _ = agent_runtime
    agent = create()
    agent.chat("first")
    history = [
        ChatMessage(role="user", content="old user"),
        ChatMessage(role="assistant", content="old answer"),
    ]
    if method == "achat":
        asyncio.run(agent.achat("next", chat_history=history))
    else:
        agent.chat("next", chat_history=history)
    assert requests[2]["messages"][:2] == [
        {"role": "user", "content": "old user"},
        {"role": "assistant", "content": "old answer"},
    ]
    assert agent.chat_history[0].content == "old user"
    assert history[0].content == "old user"


@pytest.mark.parametrize("method", ["chat", "achat"])
def test_old_agent_sync_error_observation_and_async_exception_are_distinct(
    agent_runtime, method
):
    create, requests, calls, controls, _ = agent_runtime
    controls["error"] = True
    agent = create()
    if method == "achat":
        with pytest.raises(ValueError, match="synthetic tool failure"):
            asyncio.run(agent.achat("add"))
        assert len(requests) == 1
    else:
        response = agent.chat("add")
        assert "synthetic tool failure" in requests[1]["messages"][-1]["content"]
        assert isinstance(response.sources[0].raw_output, ValueError)
        assert response.sources[0].is_error is False
        assert len(requests) == 2
    assert calls == [(2, 3)]


@pytest.mark.parametrize("limit", [0, 1])
def test_old_agent_function_call_limit_records_inclusive_legacy_boundary(
    agent_runtime, limit
):
    create, requests, calls, controls, _ = agent_runtime
    controls["repeat"] = True
    response = create(max_function_calls=limit).chat("repeat")
    # The old worker stops when previous calls > max_function_calls, not >=.
    assert len(calls) == limit + 1
    assert len(requests) == limit + 2
    assert len(response.sources) == limit + 1


def test_old_agent_rejects_conflicting_prefixes(agent_runtime):
    create, _, _, _, _ = agent_runtime
    with pytest.raises(ValueError, match="both system_prompt and prefix_messages"):
        create(
            system_prompt="one",
            prefix_messages=[ChatMessage(role="system", content="two")],
        )


@pytest.mark.parametrize("method", ["chat", "stream_chat"])
def test_old_agent_sync_methods_use_sync_provider_and_tool(
    agent_runtime, monkeypatch, method
):
    create, requests, calls, _, _ = agent_runtime

    async def reject_async(*args, **kwargs):
        raise AssertionError("A synchronous entry must use the synchronous client/tool")

    monkeypatch.setattr(OpenAI, "achat", reject_async)
    monkeypatch.setattr(OpenAI, "astream_chat", reject_async)
    monkeypatch.setattr(FunctionTool, "acall", reject_async)
    agent = create()
    for _ in range(2):
        response = getattr(agent, method)("add")
        text = "".join(response.response_gen) if "stream" in method else str(response)
        assert text == "answer 5"
        agent.reset()
    assert len(requests) == 4 and calls == [(2, 3), (2, 3)]


@pytest.mark.parametrize("method", ["chat", "achat", "stream_chat", "astream_chat"])
def test_old_agent_custom_tool_parser_keeps_original_history_and_call_ids(
    agent_runtime, method
):
    create, _, calls, controls, _ = agent_runtime
    controls["arguments"] = '{"legacy_a":2,"legacy_b":3}'
    parsed = []

    def parser(call):
        parsed.append((call.id, call.function.arguments))
        data = json.loads(call.function.arguments)
        return {"a": data["legacy_a"], "b": data["legacy_b"]}

    agent = create(tool_call_parser=parser)

    async def run():
        response = await getattr(agent, method)("add")
        if "stream" in method:
            return "".join([value async for value in response.async_response_gen()])
        return str(response)

    if method.startswith("a"):
        text = asyncio.run(run())
    else:
        response = getattr(agent, method)("add")
        text = "".join(response.response_gen) if "stream" in method else str(response)
    assert text == "answer 5" and calls == [(2, 3)]
    assert parsed == [("call-1", controls["arguments"])]
    original = agent.chat_history[1].additional_kwargs["tool_calls"][0]
    assert (
        original.id == "call-1" and original.function.arguments == controls["arguments"]
    )
