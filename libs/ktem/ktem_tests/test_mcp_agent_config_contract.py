"""Actual SQL manager and agent factories must not consume saved tool filters."""

from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import Table, create_engine

from kotaemon.agents.tools import mcp
from kotaemon.llms import ChatLLM


@pytest.fixture
def manager(tmp_path, monkeypatch):
    from ktem.mcp import manager as module

    engine = create_engine(f"sqlite:///{tmp_path / 'owned-mcp.db'}")
    cast(Table, module.MCPTable.__table__).create(engine)
    monkeypatch.setattr(module, "engine", engine)
    instance = module.MCPManager()
    try:
        yield instance
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "agent_name, class_name",
    [
        ("react", "ReactAgentPipeline"),
        ("rewoo", "RewooAgentPipeline"),
    ],
)
@pytest.mark.parametrize("enabled", [None, [], ["allowed"]])
def test_repeated_agent_construction_preserves_saved_config(
    manager, monkeypatch, agent_name, class_name, enabled
):
    module = import_module(f"ktem.reasoning.{agent_name}")
    cls = getattr(module, class_name)
    config = {"command": "owned", "enabled_tools": enabled, "env": {"FAKE": "owned"}}
    manager.add("owned", config)
    expected = deepcopy(manager.get("owned"))
    choices = manager.get_enabled_tools()
    monkeypatch.setattr(module, "mcp_manager", manager)
    fake_llm = ChatLLM()
    monkeypatch.setattr(
        module,
        "_get_llms",
        lambda: SimpleNamespace(
            get=lambda *args: fake_llm, get_default=lambda: fake_llm, options=lambda: {}
        ),
    )

    async def discover(parsed):
        assert parsed["command"] == "owned"
        return [
            mcp.MCPTool(name=name, mcp_tool_name=name) for name in ("allowed", "other")
        ]

    monkeypatch.setattr(mcp, "_async_discover_tools", discover)
    prefix = f"reasoning.options.{cls.get_info()['id']}"
    settings = {
        f"{prefix}.{key}": value["value"]
        for key, value in cls.get_user_settings().items()
    }
    settings.update({f"{prefix}.tools": ["[MCP] owned"], "reasoning.lang": "en"})
    expected_tools = ["allowed"] if enabled else ["allowed", "other"]
    for _ in range(2):
        pipeline = cls.get_pipeline(settings, {}, [])
        assert [tool.name for tool in pipeline.agent.plugins] == expected_tools
        assert manager.get("owned") == expected
        assert manager.get_enabled_tools() == choices
    manager.load()
    assert manager.get("owned") == expected


def test_real_manager_crud_and_shared_reference_semantics(manager):
    manager.add(" first ", {"command": "owned", "enabled_tools": []})
    assert list(manager.info()) == ["first"]
    assert manager.get("first") is manager.info()["first"]
    assert manager.get_enabled_tools() == ["[MCP] first"]
    manager.update("first", {"command": "changed"})
    assert manager.get_enabled_tools() == []
    manager.load()
    assert manager.get("first")["config"] == {"command": "changed"}
    manager.delete("first")
    assert manager.info() == {}
    manager.delete("absent")
    with pytest.raises(ValueError, match="Name must not be empty"):
        manager.add(" ", {})
    with pytest.raises(ValueError, match="not found"):
        manager.update("absent", {})
