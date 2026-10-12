"""Task-owned MCP 1.x server; never reads user MCP configuration."""

import asyncio
import json
import os
import socket
import sys
import time
from pathlib import Path


def main():
    # Establish the repository's original isolation boundary before SDK imports.
    from pytest_runtime_isolation import start_process_test_runtime

    evidence = Path(sys.argv[2]) / str(os.getpid())
    evidence.mkdir()
    runtime = start_process_test_runtime(evidence_dir=evidence)
    try:
        asyncio.run(serve(sys.argv[1], evidence))
    finally:
        runtime.close()


async def serve(transport, evidence):
    import mcp.types as types
    from mcp.server.lowlevel import Server

    def record(event, **fields):
        with (evidence / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event": event,
                        "pid": os.getpid(),
                        "at_ns": time.monotonic_ns(),
                        **fields,
                    }
                )
                + "\n"
            )

    server = Server("owned-contract")

    @server.list_tools()
    async def tools():
        record("list")
        return [
            types.Tool(
                name="owned_echo",
                description="Owned Unicode 回声",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "count": {"type": "integer", "default": 1},
                    },
                    "required": ["value"],
                },
            )
        ]

    @server.call_tool()
    async def call(name, arguments):
        record("call", name=name, arguments=arguments)
        if arguments["value"] == "error":
            raise RuntimeError("owned server error")
        if arguments["value"] == "hold":
            record("held")
            try:
                await asyncio.Event().wait()
            finally:
                record("cancelled")
        return [
            types.TextContent(
                type="text", text=json.dumps(arguments, ensure_ascii=False)
            )
        ]

    record("started")
    if transport == "exit":
        return
    if transport == "stdio":
        from mcp.server.stdio import stdio_server

        async with stdio_server() as streams:
            await server.run(*streams, server.create_initialization_options())
        record("finished")
        return

    await serve_sse(server, evidence, record)


async def serve_sse(server, evidence, record):
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/messages/")
    session_number = 0

    async def handle(request):
        nonlocal session_number
        session_number += 1
        number = session_number
        record("connected", session=number)
        try:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(*streams, server.create_initialization_options())
        finally:
            record("disconnected", session=number)
        return Response()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        config = uvicorn.Config(
            Starlette(
                routes=[
                    Route("/sse", handle),
                    Mount("/messages/", app=sse.handle_post_message),
                ]
            ),
            log_level="error",
            timeout_graceful_shutdown=2,
        )
        application = uvicorn.Server(config)

        async def ready_and_stop():
            while not application.started:
                await asyncio.sleep(0.01)
            record("ready", port=sock.getsockname()[1])
            while not (evidence.parent / "stop").exists():
                await asyncio.sleep(0.02)
            application.should_exit = True

        control = asyncio.create_task(ready_and_stop())
        try:
            await application.serve(sockets=[sock])
        finally:
            control.cancel()
            await asyncio.gather(control, return_exceptions=True)
    record("finished")


if __name__ == "__main__":
    main()
