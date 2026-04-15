"""Tests for the `get_page` MCP tool (Story 06.2-004).

Fetches full markdown content for a slug. Looks under wiki_dir first,
then wiki_dir/concepts/. Path-traversal defence is critical because
naive slug joining could leak arbitrary files.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import mcp.types as mcp_types
import pytest

from ai_research.mcp_server import server as server_module
from ai_research.mcp_server.tools import get_page as get_page_tool


@pytest.fixture
def fixture_wiki(tmp_path: Path) -> Path:
    """Fixture vault: one full page, one concept stub."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "dario-amodei.md").write_text(
        "---\ntitle: Dario Amodei\nstub: false\n---\n# Dario Amodei\n\nCEO of Anthropic.\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "scaling-laws.md").write_text(
        "---\ntitle: Scaling Laws\nstub: true\n---\n# Scaling Laws\n\nStub.\n",
        encoding="utf-8",
    )
    return wiki


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_get_page_registered_in_list_tools() -> None:
    srv = server_module.build_server()

    async def call() -> list[mcp_types.Tool]:
        req = mcp_types.ListToolsRequest(method="tools/list")
        handler = srv.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(req)
        return result.root.tools  # type: ignore[attr-defined,no-any-return]

    tools = _run(call())
    names = [t.name for t in tools]
    assert "get_page" in names
    defn = next(t for t in tools if t.name == "get_page")
    assert "slug" in defn.inputSchema["properties"]
    assert "include_frontmatter" in defn.inputSchema["properties"]
    assert "wiki_dir" in defn.inputSchema["properties"]
    assert defn.inputSchema["required"] == ["slug"]


def test_get_page_returns_full_wiki_page(fixture_wiki: Path) -> None:
    result = _run(
        get_page_tool.handle({"slug": "dario-amodei", "wiki_dir": str(fixture_wiki)}),
    )
    assert result["slug"] == "dario-amodei"
    assert result["path"] == "wiki/dario-amodei.md"
    assert "CEO of Anthropic." in result["content"]
    # default include_frontmatter=True preserves YAML block
    assert result["content"].startswith("---")


def test_get_page_falls_back_to_concepts(fixture_wiki: Path) -> None:
    result = _run(
        get_page_tool.handle({"slug": "scaling-laws", "wiki_dir": str(fixture_wiki)}),
    )
    assert result["slug"] == "scaling-laws"
    assert result["path"] == "wiki/concepts/scaling-laws.md"
    assert "Stub." in result["content"]


def test_get_page_strip_frontmatter(fixture_wiki: Path) -> None:
    result = _run(
        get_page_tool.handle(
            {
                "slug": "dario-amodei",
                "include_frontmatter": False,
                "wiki_dir": str(fixture_wiki),
            },
        ),
    )
    assert not result["content"].startswith("---")
    assert "title: Dario Amodei" not in result["content"]
    assert "# Dario Amodei" in result["content"]
    assert "CEO of Anthropic." in result["content"]


def test_get_page_unknown_slug_raises(fixture_wiki: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no-such-page"):
        _run(
            get_page_tool.handle(
                {"slug": "no-such-page", "wiki_dir": str(fixture_wiki)},
            ),
        )


def test_get_page_missing_slug_raises(fixture_wiki: Path) -> None:
    with pytest.raises(ValueError, match="slug"):
        _run(get_page_tool.handle({"wiki_dir": str(fixture_wiki)}))


def test_get_page_empty_slug_raises(fixture_wiki: Path) -> None:
    with pytest.raises(ValueError, match="slug"):
        _run(get_page_tool.handle({"slug": "", "wiki_dir": str(fixture_wiki)}))


@pytest.mark.parametrize(
    "bad_slug",
    [
        "../etc/passwd",
        "..",
        "../dario-amodei",
        "/etc/passwd",
        "foo/bar",
        "concepts/scaling-laws",  # slug must not contain path separators
        "foo\\bar",
        "foo\x00bar",
        "./foo",
        "-leading-dash",  # must start with alphanumeric
        "UPPER",  # enforce lowercase slug regex
    ],
)
def test_get_page_rejects_path_traversal(fixture_wiki: Path, bad_slug: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        _run(
            get_page_tool.handle({"slug": bad_slug, "wiki_dir": str(fixture_wiki)}),
        )


def test_get_page_missing_wiki_dir_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-wiki"
    with pytest.raises(FileNotFoundError):
        _run(get_page_tool.handle({"slug": "foo", "wiki_dir": str(missing)}))


def test_get_page_uses_env_var_when_no_override(
    monkeypatch: pytest.MonkeyPatch, fixture_wiki: Path
) -> None:
    root = fixture_wiki.parent
    monkeypatch.setenv("AI_RESEARCH_ROOT", str(root))
    result = _run(get_page_tool.handle({"slug": "dario-amodei"}))
    assert result["slug"] == "dario-amodei"
