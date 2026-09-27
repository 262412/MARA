"""Real owned stdio/SSE sessions through production discovery and agent calls."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from kotaemon.agents import ReactAgent
from kotaemon.agents.tools.mcp import (
    MCPTool,
    async_discover_tools_info,
    create_tools_from_config,
    discover_tools_info,
)
from kotaemon.base import Document
from kotaemon.llms import BaseLLM
from pytest_runtime_isolation import ISOLATED_RUNTIME_ENV_KEYS


class ScriptedLLM(BaseLLM):
    replies: list[str] = []

    def run(self, prompt, **kwargs):
        return Document(text=self.replies.pop(0))


def records(root):
    events = [
        json.loads(line)
        for path in root.glob("*/events.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    # Directory/PID order is not invocation order across stdio processes.
    return sorted(events, key=lambda item: item["at_ns"])


def until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("Owned MCP operation did not reach its endpoint")


@pytest.fixture(params=["stdio", "sse"])
def owned_server(request, tmp_path, mara_test_runtime_paths):
    root = mara_test_runtime_paths.root
    keys = (*ISOLATED_RUNTIME_ENV_KEYS, "PATH", "SYSTEMROOT", "WINDIR")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(
        MARA_DIAGNOSTIC_ISOLATION_REQUIRED="1",
        MARA_DIAGNOSTIC_CHILD="1",
        MARA_PYTEST_OWNER_TOKEN=(root / ".mara-pytest-owner").read_text(),
        MARA_PYTEST_RUNTIME_PARENT=str(root / "children"),
    )
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        env[key] = str(tmp_path)
    script = Path(__file__).with_name("mcp_owned_server.py")
    command = [sys.executable, "-B", str(script), request.param, str(tmp_path)]
    config = {
        "transport": "stdio",
        "command": sys.executable,
        "args": command[1:],
        "env": env,
    }
    process = None
    port = None
    with (tmp_path / "server.log").open("w", encoding="utf-8") as log:
        try:
            if request.param == "sse":
                process = subprocess.Popen(
                    command, env=env, stdout=log, stderr=log, cwd=tmp_path
                )

                def ready():
                    assert process.poll() is None, (tmp_path / "server.log").read_text()
                    return next(
                        (r for r in records(tmp_path) if r["event"] == "ready"), None
                    )

                port = until(ready)["port"]
                config = {"transport": "sse", "url": f"http://127.0.0.1:{port}/sse"}
            yield config, tmp_path
        finally:
            if process is not None:
                (tmp_path / "stop").write_text("stop")
                try:
                    assert process.wait(timeout=10) == 0
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
            until(
                lambda: all(not psutil.pid_exists(r["pid"]) for r in records(tmp_path))
            )
            if port:
                with socket.socket() as check:
                    assert check.connect_ex(("127.0.0.1", port)) != 0
            print(
                json.dumps(
                    {
                        "transport": request.param,
                        "events": records(tmp_path),
                        "server_pids_absent": True,
                        "port_closed": bool(port),
                    }
                )
            )


def test_discovery_base_tool_and_agent_call(owned_server):
    config, evidence = owned_server
    assert discover_tools_info(config) == [
        {"name": "owned_echo", "description": "Owned Unicode 回声"}
    ]
    tools = create_tools_from_config(config)
    assert json.loads(tools[0].run('{"value":"中文","count":2}')) == {
        "value": "中文",
        "count": 2,
    }
    assert json.loads(tools[0].run("plain")) == {"value": "plain"}

    llm = ScriptedLLM(
        replies=[
            "Thought: owned\nAction: owned_echo\n" 'Action Input: {"value":"agent"}',
            "Final Answer: owned done",
        ]
    )
    agent = ReactAgent(llm=llm, plugins=tools, max_iterations=2)
    result = agent.run("Use owned_echo")
    assert result.status == "finished"
    assert result.intermediate_steps is not None
    assert json.loads(result.intermediate_steps[0][1]) == {"value": "agent"}
    calls = [r["arguments"] for r in records(evidence) if r["event"] == "call"]
    assert calls == [
        {"value": "中文", "count": 2},
        {"value": "plain"},
        {"value": "agent"},
    ]


def test_server_error_and_native_async(owned_server):
    config, evidence = owned_server

    async def exercise():
        assert len(await async_discover_tools_info(config)) == 1
        tool = create_tools_from_config(config)[0]
        assert "MCP Tool Error:" in await tool._arun_tool(value="error")
        assert json.loads(await tool._arun_tool(value="async")) == {"value": "async"}

    asyncio.run(exercise())
    assert [
        r["arguments"]["value"] for r in records(evidence) if r["event"] == "call"
    ] == ["error", "async"]


def test_cancellation_after_server_held(owned_server):
    config, evidence = owned_server
    tool = create_tools_from_config(config)[0]

    async def cancel():
        task = asyncio.create_task(tool._arun_tool(value="hold"))
        try:
            await asyncio.to_thread(
                until, lambda: any(r["event"] == "held" for r in records(evidence))
            )
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(cancel())
    if config["transport"] == "sse":
        port = int(config["url"].split(":")[2].split("/")[0])
        until(
            lambda: not any(
                c.raddr and c.raddr.port == port and c.status == psutil.CONN_ESTABLISHED
                for c in psutil.Process().net_connections(kind="tcp")
            )
        )
    else:
        until(lambda: all(not psutil.pid_exists(r["pid"]) for r in records(evidence)))
    assert sum(r["event"] == "held" for r in records(evidence)) == 1
    print(
        json.dumps({"after_client_cancellation_before_fixture_stop": records(evidence)})
    )


def test_early_exit_or_missing_sse_endpoint(owned_server):
    config, evidence = owned_server
    if config["transport"] == "stdio":
        config["args"][2] = "exit"
    else:
        config["url"] = config["url"].removesuffix("sse") + "missing"
    with pytest.raises(Exception) as caught:
        discover_tools_info(config)
    assert "MCP Tool Error" not in str(caught.value)
    assert sum(r["event"] == "started" for r in records(evidence)) == 1


def test_connection_failure_is_not_a_tool_error(tmp_path):
    tool = MCPTool(server_command=str(tmp_path / "missing-owned-server"))
    with pytest.raises(OSError):
        tool.run({})
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        tool = MCPTool(
            server_transport="sse", server_command=f"http://127.0.0.1:{port}/sse"
        )
        with pytest.raises(Exception) as caught:
            asyncio.run(tool._arun_tool())
        assert "MCP Tool Error" not in str(caught.value)
