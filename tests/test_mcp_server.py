"""Tests for the MCP stdio server bootstrap (Story 06.1-001).

These tests verify only the wiring: the module imports, `main` is callable,
and a `Server` instance can be constructed without entering the stdio loop.
Tool registration and bootstrap behaviour are covered in later stories.
"""

from __future__ import annotations

import inspect

from mcp.server import Server

from ai_research.mcp_server import server as mcp_server_module
from ai_research.mcp_server.server import SERVER_NAME, SERVER_VERSION, build_server, main


def test_main_is_callable() -> None:
    """The console-script entry point must be a callable `main()`."""
    assert callable(main)
    # No required positional args — entry-points call it with none.
    sig = inspect.signature(main)
    required = [p for p in sig.parameters.values() if p.default is inspect.Parameter.empty]
    assert required == []


def test_build_server_returns_mcp_server_instance() -> None:
    """`build_server` must produce a usable `mcp.server.Server`."""
    srv = build_server()
    assert isinstance(srv, Server)
    assert srv.name == SERVER_NAME


def test_server_advertises_version_and_init_options() -> None:
    """The server must expose initialization options (capabilities handshake)."""
    srv = build_server()
    init_opts = srv.create_initialization_options()
    assert init_opts.server_name == SERVER_NAME
    assert SERVER_VERSION  # non-empty


def test_module_exposes_main_symbol() -> None:
    """`main` is the documented entry point — keep it importable."""
    assert hasattr(mcp_server_module, "main")
