"""Tests for the `search` MCP tool (Story 06.2-002).

Thin wrapper around `ai_research.search.run_search`: verify tool
registration surfaces a `search` tool via `list_tools`, that the handler
returns structured hits, and that error paths (missing wiki_dir, empty
query) produce clean MCP errors.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import mcp.types as mcp_types
import pytest

from ai_research.mcp_server import server as server_module
from ai_research.mcp_server.tools import search as search_tool


@pytest.fixture
def fixture_wiki(tmp_path: Path) -> Path:
    """Small fixture vault with a handful of lexical hits."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "alpha.md").write_text(
        "# Alpha\n\nThe quick brown foo jumps.\nAnother line about foo.\n",
        encoding="utf-8",
    )
    (wiki / "beta.md").write_text("# Beta\n\nNo hits here.\n", encoding="utf-8")
    return wiki


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_search_tool_registered_in_list_tools() -> None:
    """After building the server, `search` must appear in the tool list."""
    srv = server_module.build_server()

    async def call() -> list[mcp_types.Tool]:
        req = mcp_types.ListToolsRequest(method="tools/list")
        handler = srv.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(req)
        return result.root.tools  # type: ignore[attr-defined,no-any-return]

    tools = _run(call())
    names = [t.name for t in tools]
    assert "search" in names
    search_def = next(t for t in tools if t.name == "search")
    assert "query" in search_def.inputSchema["properties"]
    assert "limit" in search_def.inputSchema["properties"]
    assert "wiki_dir" in search_def.inputSchema["properties"]
    assert search_def.inputSchema["required"] == ["query"]


def test_search_handler_returns_hits(fixture_wiki: Path) -> None:
    """Handler returns a structured dict of hits for a known query."""
    result = _run(
        search_tool.handle({"query": "foo", "wiki_dir": str(fixture_wiki)}),
    )
    assert "hits" in result
    hits = result["hits"]
    assert isinstance(hits, list)
    assert len(hits) == 2
    for hit in hits:
        assert set(hit.keys()) == {"page", "line", "snippet"}
        assert "foo" in hit["snippet"].lower()


def test_search_handler_respects_limit(fixture_wiki: Path) -> None:
    result = _run(
        search_tool.handle(
            {"query": "foo", "limit": 1, "wiki_dir": str(fixture_wiki)},
        ),
    )
    assert len(result["hits"]) == 1


def test_search_handler_default_limit_is_twenty(fixture_wiki: Path) -> None:
    """AC: default limit is 20 when not provided."""
    assert search_tool.DEFAULT_LIMIT == 20


def test_search_handler_empty_query_raises(fixture_wiki: Path) -> None:
    with pytest.raises(ValueError, match="query"):
        _run(search_tool.handle({"query": "", "wiki_dir": str(fixture_wiki)}))


def test_search_handler_whitespace_query_raises(fixture_wiki: Path) -> None:
    with pytest.raises(ValueError, match="query"):
        _run(search_tool.handle({"query": "   ", "wiki_dir": str(fixture_wiki)}))


def test_search_handler_missing_wiki_dir_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-wiki"
    with pytest.raises(FileNotFoundError):
        _run(search_tool.handle({"query": "foo", "wiki_dir": str(missing)}))


def test_search_handler_uses_env_var_when_no_override(
    monkeypatch: pytest.MonkeyPatch, fixture_wiki: Path
) -> None:
    """When no `wiki_dir` argument, AI_RESEARCH_ROOT resolves to <root>/wiki."""
    root = fixture_wiki.parent
    monkeypatch.setenv("AI_RESEARCH_ROOT", str(root))
    result = _run(search_tool.handle({"query": "foo"}))
    assert len(result["hits"]) == 2


def test_search_handler_no_root_configured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no env var and no override, handler raises a clear error."""
    monkeypatch.delenv("AI_RESEARCH_ROOT", raising=False)
    # cwd won't have a `wiki` dir in the pytest tmp environment by default
    monkeypatch.chdir("/tmp")
    with pytest.raises(FileNotFoundError):
        _run(search_tool.handle({"query": "foo"}))
