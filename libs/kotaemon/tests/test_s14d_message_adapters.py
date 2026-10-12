"""Message exchange separates provider fields from persisted document records."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.messages import HumanMessage as LCHumanMessage
from langchain_core.messages import SystemMessage as LCSystemMessage
from langchain_core.messages import ToolMessage

from kotaemon.base import schema
from kotaemon.base.message_adapters import from_langchain_message, to_langchain_message

PAYLOADS = json.loads(
    (Path(__file__).parent / "resources/legacy_message_payloads.json").read_text()
)


@pytest.mark.parametrize(
    "name,native",
    [
        ("SystemMessage", LCSystemMessage),
        ("HumanMessage", LCHumanMessage),
        ("AIMessage", LCAIMessage),
    ],
)
def test_explicit_identity_migration_and_independent_native_objects(name, native):
    internal = getattr(schema, name).from_dict(deepcopy(PAYLOADS[name]))
    assert isinstance(internal, schema.Document)
    assert isinstance(internal, native)
    assert issubclass(type(internal), native)
    external = to_langchain_message(internal)
    assert type(external) is native
    assert external.id == "provider-message-id"
    assert "metadata" not in external.dict() and "id_" not in external.dict()
    assert "private.pdf" not in json.dumps(external.dict())
    assert external.content == internal.content
    assert external.additional_kwargs == internal.additional_kwargs
    assert external.response_metadata == internal.response_metadata
    external.additional_kwargs["provider_extension"]["value"] = 7
    assert internal.additional_kwargs["provider_extension"]["value"] == 1
    restored = from_langchain_message(to_langchain_message(internal))
    assert restored.doc_id != restored.id
    assert restored.doc_id != internal.doc_id
    assert (
        to_langchain_message(restored).dict() == to_langchain_message(internal).dict()
    )


@pytest.mark.parametrize("name", ["LLMInterface", "StructuredOutputLLMInterface"])
def test_raw_nested_legacy_json_is_readable_and_serializable(name):
    payload = deepcopy(PAYLOADS[name])
    restored = getattr(schema, name).from_dict(payload)
    assert restored.to_dict() == PAYLOADS[name]
    assert payload == PAYLOADS[name]
    assert isinstance(restored.messages[0], schema.AIMessage)
    assert isinstance(restored.messages[0], LCAIMessage)


def test_native_nested_live_object_needs_explicit_conversion():
    external = LCAIMessage(content="text", id="provider")
    with pytest.raises((ValueError, TypeError)):
        schema.LLMInterface(content="text", messages=[external])
    assert (
        schema.LLMInterface(content="text", messages=[from_langchain_message(external)])
        .messages[0]
        .id
        == "provider"
    )


def test_stream_tool_chunks_and_usage_are_preserved():
    native = AIMessageChunk(
        content="",
        id="stream",
        tool_call_chunks=[
            {"name": "lookup", "args": '{"q":', "id": "call", "index": 0}
        ],
        usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
    )
    model = from_langchain_message(native)
    assert model.tool_call_chunks == native.tool_call_chunks
    assert model.tool_calls == native.tool_calls
    assert model.usage_metadata == native.usage_metadata
    assert to_langchain_message(model).dict() == native.dict()


def test_legacy_extra_fields_have_explicit_boundary_policy():
    original = schema.AIMessage("answer", tool_call_id="call-7")
    assert to_langchain_message(original).tool_call_id == "call-7"
    unknown = schema.AIMessage("answer", provider_extra={"x": 1})
    assert unknown.to_dict()["provider_extra"] == {"x": 1}
    with pytest.raises(ValueError, match="Unmapped"):
        to_langchain_message(unknown)
    with pytest.raises(ValueError, match="Unmapped"):
        from_langchain_message(
            LCAIMessage(content="answer", metadata={"private": "path"})
        )


@pytest.mark.parametrize(
    "value",
    [schema.BaseMessage("base"), object(), {"role": "human", "content": "text"}],
)
def test_invalid_internal_input_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        to_langchain_message(value)


def test_invalid_native_input_and_corrupted_typed_fields_are_revalidated():
    with pytest.raises(ValueError, match="Unsupported"):
        from_langchain_message(
            ToolMessage(content="not-a-supported-internal-role", tool_call_id="call")
        )
    invalid = LCAIMessage.construct(
        content="text", tool_calls=[{"name": "x", "args": "wrong", "id": "c"}]
    )
    with pytest.raises((ValueError, TypeError)):
        from_langchain_message(invalid)
    with pytest.raises((ValueError, TypeError)):
        to_langchain_message(schema.AIMessage(object()))


def test_legacy_tool_call_parser_runs_with_native_validation():
    model = schema.AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "c",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": '{"q":"value"}'},
                }
            ]
        },
    )
    assert model.tool_calls == [
        {"name": "lookup", "args": {"q": "value"}, "id": "c", "type": "tool_call"}
    ]
    assert to_langchain_message(model).tool_calls == model.tool_calls


def test_parallel_conversions_do_not_share_mutable_data():
    original = schema.AIMessage.from_dict(deepcopy(PAYLOADS["AIMessage"]))

    def convert(index):
        model = from_langchain_message(to_langchain_message(original))
        model.tool_calls[0]["args"]["index"] = index
        return model

    with ThreadPoolExecutor(max_workers=4) as pool:
        models = list(pool.map(convert, range(12)))
    assert len({model.doc_id for model in models}) == 12
    assert "index" not in original.tool_calls[0]["args"]
    assert [model.tool_calls[0]["args"]["index"] for model in models] == list(range(12))


def test_exports_agent_fields_and_mcp_argument_validation():
    from kotaemon.agents.io import AgentOutput, AgentType
    from kotaemon.agents.tools.mcp import build_args_model

    agent = AgentOutput(text="answer", agent_type=AgentType.react, status="finished")
    assert agent.text == agent.content == "answer"
    assert agent.to_dict()["model_config"] == {"extra": "allow"}
    with pytest.raises(ValueError):
        AgentOutput(text="answer", agent_type="invalid", status="finished")
    model = build_args_model(
        "lookup",
        {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["q"],
        },
    )
    assert model.model_validate({"q": "text"}).model_dump()["limit"] == 3
    with pytest.raises(ValueError):
        model.model_validate({"q": "text", "limit": "wrong"})
