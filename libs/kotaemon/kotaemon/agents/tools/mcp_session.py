"""Own one stdio/SSE connection and initialized SDK session per operation."""

from contextlib import asynccontextmanager


@asynccontextmanager
async def initialized_session(
    transport: str, command: str, args: list[str], env: dict[str, str]
):
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.stdio import StdioServerParameters, stdio_client

    if transport == "stdio":
        connection = stdio_client(
            StdioServerParameters(command=command, args=args, env=env or None)
        )
    elif transport == "sse":
        connection = sse_client(url=command)
    else:
        raise ValueError(f"Unsupported transport: {transport}")

    async with connection as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
