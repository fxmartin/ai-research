"""Minimal MCP stdio server bootstrap.

Story 06.1-001 scope: construct a `Server` instance and run the stdio loop.
No tools are registered yet — `ask`, `search`, `list_pages`, `get_page`
arrive in Epic-06 Feature 06.2. Bootstrap (vault root, schema, state) lands
in story 06.1-002.
"""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server

SERVER_NAME = "ai-research"
SERVER_VERSION = "0.1.0"


def build_server() -> Server:
    """Construct the MCP `Server` instance.

    Kept separate from `main` so tests can assert the server is
    constructable without entering the stdio event loop.
    """
    return Server(SERVER_NAME, version=SERVER_VERSION)


async def _run() -> None:
    """Run the MCP server over stdio until the client disconnects."""
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
