"""MCP (Model Context Protocol) stdio server for ai-research.

Exposes the wiki as read-only MCP tools for Claude Desktop and other
MCP-aware clients. This is the Epic-06 surface. Tools are registered in
subsequent stories (06.1-002 and 06.2-*). This story (06.1-001) only wires
the entry point and SDK dependency.
"""

from ai_research.mcp_server.context import (
    ServerContext,
    build_context,
    get_context,
    set_context,
)
from ai_research.mcp_server.server import build_server, main

__all__ = [
    "ServerContext",
    "build_context",
    "build_server",
    "get_context",
    "main",
    "set_context",
]
