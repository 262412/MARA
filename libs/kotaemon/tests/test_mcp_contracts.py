"""Existing MCP facade and SDK patch contracts, before session extraction."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from kotaemon.agents.tools import mcp


@pytest.fixture
def sdk(monkeypatch):
    import mcp as sdk_module
    import mcp.client.sse
    import mcp.client.stdio

    events = []
    infos = [
        SimpleNamespace(name="second", description=None, inputSchema={}),
        SimpleNamespace(
            name="first", description="First", inputSchema={"type": "object"}
        ),
    ]

    def record(name, value=None):
        events.append((name, value, asyncio.current_task(), asyncio.get_running_loop()))

    @asynccontextmanager
    async def transport(value=None, **kwargs):
        record("connect", value or kwargs)
        try:
            yield "read", "write"
        finally:
            record("disconnect")

    class Session:
        def __init__(self, read, write):
            assert (read, write) == ("read", "write")

        async def __aenter__(self):
            record("enter")
            return self

        async def __aexit__(self, *exc):
            record("exit", exc[1])

        async def initialize(self):
            record("initialize")

        async def list_tools(self):
            record("list")
            return SimpleNamespace(tools=infos)

        async def call_tool(self, name, arguments):
            record("call", (name, arguments))
            return SimpleNamespace(isError=False, content=[SimpleNamespace(text="ok")])

    monkeypatch.setattr(sdk_module, "ClientSession", Session)
    monkeypatch.setattr(mcp.client.stdio, "stdio_client", transport)
    monkeypatch.setattr(mcp.client.sse, "sse_client", transport)
    return events


@pytest.mark.parametrize("transport", ["stdio", "sse"])
@pytest.mark.parametrize("entry", ["wrapped", "info", "call"])
def test_session_order_and_task_ownership(sdk, transport, entry):
    config = {"transport": transport, "command": "owned", "url": "http://owned"}
    if entry == "wrapped":
        result = mcp.create_tools_from_config(config)
        assert [tool.name for tool in result] == ["second", "first"]
        assert result[0].description == "MCP tool: second"
        assert result[0].args_schema is None
    elif entry == "info":
        assert mcp.discover_tools_info(config) == [
            {"name": "second", "description": ""},
            {"name": "first", "description": "First"},
        ]
    else:
        tool = mcp.MCPTool(server_transport=transport, server_command="owned")
        assert tool.run({"x": 1}) == "ok"
    assert [event[0] for event in sdk] == [
        "connect",
        "enter",
        "initialize",
        "call" if entry == "call" else "list",
        "exit",
        "disconnect",
    ]
    assert len({id(event[2]) for event in sdk}) == 1
    assert len({id(event[3]) for event in sdk}) == 1


@pytest.mark.parametrize(
    "enabled, expected",
    [
        (None, ["second", "first"]),
        ([], ["second", "first"]),
        (["first", "second", "absent"], ["second", "first"]),
        (["first"], ["first"]),
        (["absent"], []),
    ],
)
def test_discovery_filter_preserves_server_order(sdk, enabled, expected):
    tools = mcp.create_tools_from_config({"command": "owned"}, enabled)
    assert [tool.name for tool in tools] == expected


def test_parse_references_and_direct_command_split(sdk):
    args, env = ["fixed arg"], {"OWNED": "fake"}
    config = {"command": "full command", "args": args, "env": env}
    parsed = mcp.parse_mcp_config(config)
    assert parsed["args"] is args and parsed["env"] is env
    assert parsed["command"] == "full command"
    assert mcp.parse_mcp_config({"command": 'owned "two words"'})["args"] == [
        "two words"
    ]
    tool = mcp.MCPTool(server_command='owned "two words"')
    assert tool.run("hello") == "ok"
    assert sdk[0][1].command == "owned"
    assert sdk[0][1].args == ["two words"]
    assert sdk[0][1].env is None
    assert sdk[3][1] == ("", {"input": "hello"})


@pytest.mark.parametrize(
    "value, expected",
    [
        ({"query": "dict"}, {"query": "dict"}),
        ('{"query":"json","limit":3}', {"query": "json", "limit": 3}),
        ("plain", {"query": "plain"}),
    ],
)
def test_base_tool_input_and_default_omission(sdk, value, expected):
    schema = mcp.build_args_model(
        "owned",
        {
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 9},
            },
            "required": ["query"],
        },
    )
    tool = mcp.MCPTool(server_command="owned", args_schema=schema)
    assert tool.run(value) == "ok"
    assert sdk[3][1] == ("", expected)


def test_invalid_input_fails_before_connection(sdk):
    schema = mcp.build_args_model("empty", {"type": "object"})
    tool = mcp.MCPTool(server_command="owned", args_schema=schema)
    with pytest.raises(IndexError):
        tool.run("plain")
    assert sdk == []
    with pytest.raises(ValueError):
        mcp.parse_mcp_config({"command": 'owned "unclosed'})


def test_unknown_transport_and_formatting(sdk):
    assert mcp.create_tools_from_config({"transport": "unknown"}) == []
    assert mcp.discover_tools_info({"transport": "unknown"}) == []
    tool = mcp.MCPTool(server_transport="unknown")
    assert tool.run({}) == "Unsupported transport: unknown"
    assert sdk == []
    result = SimpleNamespace(
        isError=False,
        content=[
            SimpleNamespace(text="first"),
            SimpleNamespace(data="x", mimeType="image/png"),
            12,
        ],
    )
    assert tool._format_result(result) == "first\n[Binary data: image/png]\n12"
    assert tool._format_result(SimpleNamespace(isError=True, content="bad")) == (
        "MCP Tool Error: bad"
    )
