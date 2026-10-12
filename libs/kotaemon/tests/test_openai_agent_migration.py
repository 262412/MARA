"""Exact configuration migration and owned stream cancellation for the candidate."""

import asyncio
import json
from copy import deepcopy

import pytest
from pydantic import BaseModel

from kotaemon.agents.openai import OpenAIAgent

from . import test_openai_agent_contracts as agent_contracts

agent_runtime = agent_contracts.agent_runtime


def test_configured_vendor_and_serialized_class_reference_migrate_exactly(
    agent_runtime, monkeypatch, caplog
):
    from ktem.llms.config import migrate_legacy_agent_spec
    from ktem.llms.manager import LLMManager
    from theflow.settings import settings
    from theflow.utils.modules import deserialize

    old = "llama_index.agent.openai.OpenAIAgent"
    monkeypatch.setattr(settings, "KH_LLM_EXTRA_VENDORS", [old], raising=False)
    manager = LLMManager.__new__(LLMManager)
    manager.load_vendors()
    assert manager._vendors[-1] is OpenAIAgent
    reference = "{{ " + old + " }}"
    assert deserialize(migrate_legacy_agent_spec(reference), safe=False) is OpenAIAgent
    assert reference == "{{ llama_index.agent.openai.OpenAIAgent }}"
    create, _, _, _, _ = agent_runtime
    runtime = create()
    agent = manager._vendors[-1].from_tools(
        tools=runtime._settings["tools"], llm=runtime.llm, memory=runtime.memory
    )
    assert str(agent.chat("configured class")) == "answer 5"
    assert "Migrating saved model classpath" in caplog.text


class SavedAddParameters(BaseModel):
    a: int
    b: int


def saved_add(a: int, b: int) -> int:
    return a + b


def saved_spec():
    return {
        "__type__": "llama_index.agent.openai.OpenAIAgent",
        "tools": [
            {
                "__type__": "llama_index.core.tools.FunctionTool",
                "fn": "{{ " + __name__ + ".saved_add }}",
                "metadata": {
                    "__type__": "llama_index.core.tools.ToolMetadata",
                    "name": "add",
                    "description": "Saved addition",
                    "fn_schema": "{{ " + __name__ + ".SavedAddParameters }}",
                },
            }
        ],
        "llm": {
            "__type__": "llama_index.llms.openai.OpenAI",
            "model": "gpt-4o-mini",
            "api_key": "synthetic-key",
            "api_base": "https://example.invalid/v1",
            "max_retries": 0,
        },
        "memory": {
            "__type__": "llama_index.core.memory.ChatMemoryBuffer",
            "token_limit": 10000,
            "tokenizer_fn": "{{ builtins.list }}",
        },
        "prefix_messages": [],
    }


@pytest.mark.parametrize("boundary", ["model_pool", "manager"])
def test_saved_old_classpath_loads_at_first_party_boundary_without_rewriting_data(
    agent_runtime, caplog, boundary
):
    create, requests, _, _, _ = agent_runtime
    reference = create()
    original = json.loads(json.dumps(saved_spec()))
    for _ in range(2):
        config = deepcopy(original)
        if boundary == "model_pool":
            from ktem.components import ModelPool

            agent = ModelPool("agent", {"saved": {"spec": config}})["saved"]
        else:
            from ktem.llms.manager import LLMManager

            manager = LLMManager.__new__(LLMManager)
            manager._models, manager._info, manager._load_errors = (
                {},
                {"saved": {"spec": config}},
                [],
            )
            agent = manager["saved"]
        assert isinstance(agent, OpenAIAgent)
        assert config == original
        agent.llm._http_client = reference.llm._http_client
        agent.llm._async_http_client = reference.llm._async_http_client
        assert str(agent.chat("saved tool")) == "answer 5"
        assert agent.chat_history[-1].content == "answer 5"
    assert len(requests) == 4
    assert (
        "Migrating saved model classpath llama_index.agent.openai.OpenAIAgent"
        in caplog.text
    )


@pytest.mark.parametrize(
    "path",
    [
        "llama_index.agent.openai.Other",
        "llama_index.agent.openai.OpenAIAgent.extra",
        "other.OpenAIAgent",
    ],
)
def test_similar_classpaths_are_not_migrated(path, caplog):
    from ktem.llms.config import migrate_legacy_agent_spec
    from theflow.utils.modules import deserialize

    with pytest.raises((ImportError, AttributeError)):
        deserialize(migrate_legacy_agent_spec({"__type__": path}), safe=False)
    assert "Migrating saved model classpath" not in caplog.text
    assert deserialize(
        migrate_legacy_agent_spec({"__type__": "builtins.dict", "value": 3}), safe=False
    ) == {"value": 3}


@pytest.mark.parametrize("boundary", ["vendor", "reference", "model_pool", "manager"])
def test_retired_multimodal_entry_is_rejected_without_changing_saved_spec(boundary):
    from ktem.components import ModelPool
    from ktem.llms.config import (
        migrate_legacy_agent_classpath,
        migrate_legacy_agent_spec,
    )
    from ktem.llms.manager import LLMManager

    path = "llama_index.multi_modal_llms.openai.OpenAIMultiModal"
    spec = {"__type__": path, "model": "old-model"}
    original = deepcopy(spec)
    with pytest.raises(ValueError, match="OpenAIMultiModal.*retired"):
        if boundary == "vendor":
            migrate_legacy_agent_classpath(path)
        elif boundary == "reference":
            migrate_legacy_agent_spec("{{ " + path + " }}")
        elif boundary == "model_pool":
            ModelPool("retired", {"saved": {"spec": spec}})["saved"]
        else:
            manager = LLMManager.__new__(LLMManager)
            manager._models, manager._info, manager._load_errors = (
                {},
                {"saved": {"spec": spec}},
                [],
            )
            manager["saved"]
    assert spec == original
    if boundary == "manager":
        assert manager._models == {}
        assert "retired" in manager._info["saved"]["load_error"]


def test_async_stream_close_cancels_running_tool_and_releases_memory(agent_runtime):
    create, _, calls, controls, _ = agent_runtime
    agent = create()

    async def run():
        controls.update(
            pause=True,
            started=asyncio.Event(),
            release=asyncio.Event(),
            closed=asyncio.Event(),
        )
        response = await agent.astream_chat("wait")
        await asyncio.wait_for(controls["started"].wait(), 5)
        await asyncio.wait_for(response.aclose(), 5)
        assert controls["closed"].is_set()
        assert not agent._active and agent.chat_history == []
        assert response.handler.done()
        controls["pause"] = False
        assert str(await agent.achat("again")) == "answer 5"

    asyncio.run(run())
    assert calls == [(2, 3)]


def test_consumer_cancellation_releases_async_workflow(agent_runtime):
    create, _, _, controls, _ = agent_runtime
    agent = create()

    async def run():
        controls.update(
            pause=True,
            started=asyncio.Event(),
            release=asyncio.Event(),
            closed=asyncio.Event(),
        )
        task = asyncio.create_task(agent.achat("wait"))
        await asyncio.wait_for(controls["started"].wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        await asyncio.wait_for(controls["closed"].wait(), 5)
        assert not agent._active and agent.chat_history == []

    asyncio.run(run())


def test_sync_stream_close_releases_loop_and_agent(agent_runtime):
    create, _, _, _, _ = agent_runtime
    agent = create()
    response = agent.stream_chat("add")
    tokens = response.response_gen
    assert next(tokens) == "answer"
    tokens.close()
    assert response.sync_loop.is_closed() and not agent._active
    agent.reset()


def test_error_releases_agent_and_reset_remains_usable(agent_runtime):
    create, _, _, controls, _ = agent_runtime
    agent = create()
    controls["error"] = True
    with pytest.raises(ValueError, match="synthetic tool failure"):
        asyncio.run(agent.achat("fail"))
    assert not agent._active and agent.chat_history == []
    controls["error"] = False
    assert str(agent.chat("recover")) == "answer 5"
