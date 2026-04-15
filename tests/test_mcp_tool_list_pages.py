"""Tests for the `list_pages` MCP tool (Story 06.2-003).

Verifies:
- Tool registration surfaces `list_pages` via `list_tools`.
- Parser returns the expected structured records for a fixture index.
- Empty index returns an empty list, not an error.
- Missing index.md raises a clean `FileNotFoundError`.
- Overrides (`index_path`, `wiki_dir`) and server-context fallback all work.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import mcp.types as mcp_types
import pytest

from ai_research.mcp_server import context as ctx_module
from ai_research.mcp_server import server as server_module
from ai_research.mcp_server.tools import list_pages as list_pages_tool


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_FIXTURE_INDEX = (
    "concepts/alpha.md · title: Alpha · tags: arxiv, ml · "
    "h1: Alpha; Background · links:3 · An alpha page summary.\n"
    "concepts/beta.md · title: Beta · tags:  · h1: Beta · links:0 · \n"
    "concepts/broken.md · [INVALID] · title: broken · tags:  · h1:  · links:0 · \n"
)


@pytest.fixture
def fixture_index(tmp_path: Path) -> Path:
    meta = tmp_path / ".ai-research"
    meta.mkdir()
    index_path = meta / "index.md"
    index_path.write_text(_FIXTURE_INDEX, encoding="utf-8")
    return index_path


def test_list_pages_tool_registered() -> None:
    srv = server_module.build_server()

    async def call() -> list[mcp_types.Tool]:
        req = mcp_types.ListToolsRequest(method="tools/list")
        handler = srv.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(req)
        return result.root.tools  # type: ignore[attr-defined,no-any-return]

    tools = _run(call())
    names = [t.name for t in tools]
    assert "list_pages" in names
    tool_def = next(t for t in tools if t.name == "list_pages")
    assert "wiki_dir" in tool_def.inputSchema["properties"]
    assert "index_path" in tool_def.inputSchema["properties"]
    assert tool_def.inputSchema.get("required", []) == []


def test_parse_index_structure() -> None:
    pages = list_pages_tool.parse_index(_FIXTURE_INDEX)
    assert len(pages) == 3

    alpha = pages[0]
    assert alpha == {
        "page": "concepts/alpha.md",
        "title": "Alpha",
        "tags": ["arxiv", "ml"],
        "summary": "An alpha page summary.",
        "h1s": ["Alpha", "Background"],
        "outbound_links": 3,
        "invalid": False,
    }

    beta = pages[1]
    assert beta["page"] == "concepts/beta.md"
    assert beta["tags"] == []
    assert beta["h1s"] == ["Beta"]
    assert beta["outbound_links"] == 0
    assert beta["summary"] == ""
    assert beta["invalid"] is False

    broken = pages[2]
    assert broken["invalid"] is True
    assert broken["page"] == "concepts/broken.md"


def test_parse_index_empty() -> None:
    assert list_pages_tool.parse_index("") == []
    assert list_pages_tool.parse_index("\n\n") == []


def test_handle_with_explicit_index_path(fixture_index: Path) -> None:
    result = _run(list_pages_tool.handle({"index_path": str(fixture_index)}))
    assert "pages" in result
    assert len(result["pages"]) == 3
    assert result["pages"][0]["title"] == "Alpha"


def test_handle_empty_index_returns_empty_list(tmp_path: Path) -> None:
    meta = tmp_path / ".ai-research"
    meta.mkdir()
    empty = meta / "index.md"
    empty.write_text("", encoding="utf-8")
    result = _run(list_pages_tool.handle({"index_path": str(empty)}))
    assert result == {"pages": []}


def test_handle_missing_index_raises(tmp_path: Path) -> None:
    missing = tmp_path / ".ai-research" / "index.md"
    with pytest.raises(FileNotFoundError):
        _run(list_pages_tool.handle({"index_path": str(missing)}))


def test_handle_wiki_dir_override_derives_index_path(fixture_index: Path, tmp_path: Path) -> None:
    # fixture_index lives at tmp_path/.ai-research/index.md; wiki_dir is tmp_path/wiki.
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    result = _run(list_pages_tool.handle({"wiki_dir": str(wiki_dir)}))
    assert len(result["pages"]) == 3


_SCHEMA_TOML = """
[wiki]
name = "fixture-vault"
version = 1
"""


def test_handle_uses_server_context_by_default(tmp_path: Path) -> None:
    """With no overrides, the handler reads `get_context().index_path`."""
    (tmp_path / "wiki").mkdir()
    meta = tmp_path / ".ai-research"
    meta.mkdir()
    (meta / "schema.toml").write_text(_SCHEMA_TOML, encoding="utf-8")
    (meta / "index.md").write_text(_FIXTURE_INDEX, encoding="utf-8")

    ctx = ctx_module.build_context(tmp_path, env={})
    ctx_module.set_context(ctx)
    try:
        result = _run(list_pages_tool.handle({}))
        assert len(result["pages"]) == 3
    finally:
        ctx_module.clear_context()


def test_tag_filter_returns_only_matching_pages(tmp_path: Path) -> None:
    """`tag` argument filters to pages whose tags list contains it exactly."""
    idx = tmp_path / "index.md"
    idx.write_text(
        "wiki/alpha.md · title: Alpha · tags: ai,ml · h1:  · links:0 · s\n"
        "wiki/beta.md · title: Beta · tags: politics · h1:  · links:0 · s\n"
        "wiki/gamma.md · title: Gamma · tags: ai,politics · h1:  · links:0 · s\n",
        encoding="utf-8",
    )
    out = _run(list_pages_tool.handle({"index_path": str(idx), "tag": "ai"}))
    paths = {p["page"] for p in out["pages"]}
    assert paths == {"wiki/alpha.md", "wiki/gamma.md"}


def test_prefix_filter_returns_only_matching_pages(tmp_path: Path) -> None:
    """`prefix` argument filters pages whose page path starts with prefix."""
    idx = tmp_path / "index.md"
    idx.write_text(
        "wiki/alpha.md · title: Alpha · tags:  · h1:  · links:0 · s\n"
        "wiki/concepts/foo.md · title: Foo · tags:  · h1:  · links:0 · s\n"
        "wiki/concepts/bar.md · title: Bar · tags:  · h1:  · links:0 · s\n",
        encoding="utf-8",
    )
    out = _run(list_pages_tool.handle({"index_path": str(idx), "prefix": "wiki/concepts/"}))
    paths = {p["page"] for p in out["pages"]}
    assert paths == {"wiki/concepts/foo.md", "wiki/concepts/bar.md"}


def test_tag_and_prefix_filters_compose(tmp_path: Path) -> None:
    """Both filters applied together intersect."""
    idx = tmp_path / "index.md"
    idx.write_text(
        "wiki/alpha.md · title: A · tags: ai · h1:  · links:0 · s\n"
        "wiki/concepts/foo.md · title: Foo · tags: ai · h1:  · links:0 · s\n"
        "wiki/concepts/bar.md · title: Bar · tags: politics · h1:  · links:0 · s\n",
        encoding="utf-8",
    )
    out = _run(
        list_pages_tool.handle({"index_path": str(idx), "tag": "ai", "prefix": "wiki/concepts/"})
    )
    assert [p["page"] for p in out["pages"]] == ["wiki/concepts/foo.md"]
