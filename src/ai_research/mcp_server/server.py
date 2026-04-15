"""MCP stdio server for ai-research.

Constructs the `Server` instance and registers read-only tools from
`ai_research.mcp_server.tools.*`. The registry pattern keeps tool
modules self-contained (each exposes `TOOL` + `handle`) while the
server-level `list_tools` / `call_tool` decorators aggregate them.

Stories:
- 06.1-001: entry point + stdio loop.
- 06.2-002: `search` tool wired in.
Future: 06.2-001 (`ask`), 06.2-003 (`list_pages`), 06.2-004 (`get_page`).
"""

from __future__ import annotations

import asyncio
from typing import Any

import mcp.types as mcp_types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ai_research.mcp_server.context import build_context, set_context
from ai_research.mcp_server.tools import search as search_tool

SERVER_NAME = "ai-research"
SERVER_VERSION = "0.1.0"


def build_server() -> Server:
    """Construct the MCP `Server` with all read-only tools registered."""
    server: Server = Server(SERVER_NAME, version=SERVER_VERSION)
    registry: dict[str, dict[str, Any]] = {}

    search_tool.register(registry)

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [entry["tool"] for entry in registry.values()]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        entry = registry.get(name)
        if entry is None:
            raise ValueError(f"Unknown tool: {name}")
        return await entry["handle"](arguments)

    return server


async def _run() -> None:
    """Run the MCP server over stdio until the client disconnects."""
    set_context(build_context())
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Console-script entry point for `ai-research-mcp`."""
    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
