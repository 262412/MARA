"""Synthetic baseline payloads protect public data independently of LC identity."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from kotaemon.base import schema

PAYLOADS = json.loads(
    (Path(__file__).parent / "resources" / "legacy_message_payloads.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    "name",
    [
        n
        for n in PAYLOADS
        if n
        not in ("DocumentWithEmbedding", "LLMInterface", "StructuredOutputLLMInterface")
    ],
)
def test_existing_model_payload_round_trip(name):
    payload = deepcopy(PAYLOADS[name])
    model = getattr(schema, name).from_dict(payload)

    assert json.loads(json.dumps(model.to_dict())) == PAYLOADS[name]
    assert model.dict() == model.to_dict()
    assert model.doc_id == PAYLOADS[name]["id_"]


@pytest.mark.parametrize("name", ["SystemMessage", "HumanMessage", "AIMessage"])
def test_message_document_and_provider_ids_and_aliases_are_distinct(name):
    model = getattr(schema, name).from_dict(PAYLOADS[name])
    assert model.doc_id == "legacy-document-id"
    assert model.id == "provider-message-id"
    by_alias = model.dict(by_alias=True)
    assert by_alias["doc_id"] == model.doc_id
    assert by_alias["extra_info"] == model.metadata
    assert "id_" not in by_alias
    restored = getattr(schema, name).from_dict(by_alias)
    assert restored.to_dict() == model.to_dict()


def test_message_json_keeps_tools_blocks_and_usage():
    model = schema.AIMessage.from_dict(PAYLOADS["AIMessage"])
    assert model.content[1]["type"] == "image_url"
    assert model.tool_calls[0]["id"] == "call-1"
    assert model.invalid_tool_calls[0]["args"] == "{"
    assert model.usage_metadata == {
        "input_tokens": 3,
        "output_tokens": 4,
        "total_tokens": 7,
    }
    assert model.response_metadata["headers"] == {"x-test": "yes"}
    assert model.to_openai_format() == {"role": "assistant", "content": model.content}


def test_message_extra_data_is_persisted_but_openai_payload_is_unchanged():
    model = schema.AIMessage(
        content="answer", tool_call_id="call-7", provider_extra={"value": 1}
    )
    assert model.to_dict()["tool_call_id"] == "call-7"
    assert model.to_dict()["provider_extra"] == {"value": 1}
    assert model.to_openai_format() == {"role": "assistant", "content": "answer"}
    with pytest.raises(NotImplementedError):
        model + "other"


@pytest.mark.parametrize("name", ["SystemMessage", "HumanMessage", "AIMessage"])
def test_message_requires_content_and_rejects_wrong_role(name):
    cls = getattr(schema, name)
    for fields in ({}, {"content": None}):
        with pytest.raises((TypeError, ValueError)):
            cls(**fields)
    with pytest.raises(ValueError):
        cls(content="text", type="invalid-role")


@pytest.mark.parametrize(
    "fields",
    [
        {"channel": "invalid"},
        {"embedding": ["invalid"]},
        {"tool_calls": [{"name": "lookup", "args": "invalid", "id": "c"}]},
        {"usage_metadata": {"input_tokens": "invalid"}},
    ],
)
def test_message_rejects_invalid_typed_fields(fields):
    with pytest.raises((TypeError, ValueError)):
        schema.AIMessage(content="text", **fields)


def test_nested_messages_and_structured_defaults():
    output = schema.LLMInterface.from_dict(deepcopy(PAYLOADS["LLMInterface"]))
    assert isinstance(output.messages[0], schema.AIMessage)
    assert output.messages[0].id == "provider-message-id"
    assert output.total_tokens == 7 and output.total_cost == 0.1
    assert output.logits == [[0.2]] and output.logprobs == [-0.1]
    with pytest.raises(ValueError):
        schema.LLMInterface(content="text", messages=[schema.HumanMessage("wrong")])
    assert schema.StructuredOutputLLMInterface(content="text").parsed is None


@pytest.mark.parametrize("name", ["LLMInterface", "StructuredOutputLLMInterface"])
def test_legacy_nested_json_does_not_shadow_class_name(name):
    # Nested legacy records must remain serializable after their discriminator is read.
    restored = getattr(schema, name).from_dict(deepcopy(PAYLOADS[name]))
    assert restored.messages[0].id == "provider-message-id"
    assert callable(restored.messages[0].class_name)
    assert restored.to_dict() == PAYLOADS[name]


def test_document_copy_text_and_old_embedding_reload_behavior():
    original = schema.Document.from_dict(PAYLOADS["Document"])
    copied = schema.Document(original)
    assert copied.to_dict() == original.to_dict()
    copied.metadata["copy"] = True
    assert "copy" not in original.metadata
    original.text = "updated text"
    original.content = "updated text"
    assert original.to_dict()["text"] == original.content == "updated text"
    assert original.metadata_seperator == " | "
    embedding = schema.DocumentWithEmbedding.from_dict(
        PAYLOADS["DocumentWithEmbedding"]
    )
    # The old reader renders an embedding-only content list into text on reload.
    assert embedding.content == [1.0, 2.0]
    assert embedding.text == "[1.0, 2.0]"


def test_message_mutable_defaults_are_per_instance():
    first, second = schema.LLMInterface(content="first"), schema.LLMInterface("second")
    first.additional_kwargs["first"] = True
    first.response_metadata["first"] = True
    first.tool_calls.append({"name": "lookup", "args": {}, "id": "c"})
    first.messages.append(schema.AIMessage("nested"))
    first.logprobs.append(0.1)
    assert second.additional_kwargs == second.response_metadata == {}
    assert second.tool_calls == second.messages == second.logprobs == []


def test_legacy_dict_field_selection_uses_public_names():
    message = schema.AIMessage("answer", example=True, metadata_seperator=" | ")
    assert message.dict(include={"text", "example", "metadata_seperator"}) == {
        "text": "answer",
        "example": True,
        "metadata_seperator": " | ",
        "class_name": "Document",
    }
    excluded = message.dict(exclude={"text", "example", "metadata_seperator"})
    assert not ({"text", "example", "metadata_seperator"} & excluded.keys())
    assert "text" not in schema.Document().dict(exclude_defaults=True)


def test_legacy_field_selection_respects_unset_and_agent_defaults():
    from kotaemon.agents.io import AgentOutput, AgentType

    message = schema.AIMessage("answer")
    agent = AgentOutput(text="answer", agent_type=AgentType.react, status="finished")
    empty = {"class_name": "Document"}
    for model in (message, agent):
        for field in ("example", "metadata_seperator"):
            assert model.dict(include={field}, exclude_unset=True) == empty
    assert agent.dict(include={"model_config"}) == {
        "model_config": {"extra": "allow"},
        **empty,
    }
    assert agent.dict(include={"text", "model_config"}, exclude={"model_config"}) == {
        "text": "answer",
        **empty,
    }
    assert agent.dict(include={"model_config"}, exclude_defaults=True) == empty
    assert agent.dict(include={"model_config"}, exclude_unset=True) == empty
