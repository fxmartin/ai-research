"""Tests for the MCP server bootstrap context (Story 06.1-002).

Covers:
- Happy-path bootstrap against a fixture vault.
- Env-var overrides (``AI_RESEARCH_ROOT``, ``AI_RESEARCH_WIKI_DIR``).
- Clean ``FileNotFoundError`` when the schema is missing.
- Clean ``ValueError`` when ``state.json`` is corrupt.
- Module-level singleton helpers: ``set_context`` / ``get_context`` / ``clear_context``.
- Immutability of the ``ServerContext`` dataclass.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ai_research.mcp_server.context import (
    ENV_ROOT,
    ENV_WIKI_DIR,
    ServerContext,
    build_context,
    clear_context,
    get_context,
    set_context,
)
from ai_research.schema import Schema
from ai_research.state import SourceRecord, State, save_state

_SCHEMA_TOML = """
[wiki]
name = "fixture-vault"
version = 1

[[page_templates]]
id = "source"
path_prefix = "sources/"
frontmatter_required = ["title"]

[prompts.page_draft]
sections = ["Summary"]
"""


def _make_vault(root: Path, *, with_state: bool = True) -> None:
    (root / "wiki").mkdir(parents=True, exist_ok=True)
    meta = root / ".ai-research"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "schema.toml").write_text(_SCHEMA_TOML, encoding="utf-8")
    if with_state:
        save_state(
            meta / "state.json",
            State(sources={"deadbeef": SourceRecord(page="wiki/foo.md")}),
        )


@pytest.fixture(autouse=True)
def _reset_context_singleton() -> Iterator[None]:
    clear_context()
    yield
    clear_context()


def test_build_context_loads_schema_and_state(tmp_path: Path) -> None:
    _make_vault(tmp_path)

    ctx = build_context(tmp_path, env={})

    assert isinstance(ctx, ServerContext)
    assert ctx.root == tmp_path.resolve()
    assert ctx.wiki_dir == (tmp_path / "wiki").resolve()
    assert ctx.schema_path == tmp_path / ".ai-research" / "schema.toml"
    assert ctx.state_path == tmp_path / ".ai-research" / "state.json"
    assert ctx.index_path == tmp_path / ".ai-research" / "index.md"
    assert isinstance(ctx.schema, Schema)
    assert ctx.schema.wiki.name == "fixture-vault"
    assert "deadbeef" in ctx.state.sources


def test_build_context_allows_missing_state_json(tmp_path: Path) -> None:
    _make_vault(tmp_path, with_state=False)

    ctx = build_context(tmp_path, env={})

    # Fresh vault: no state.json yet => empty State (not an error).
    assert ctx.state.sources == {}


def test_build_context_honors_env_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_vault(tmp_path)
    # cwd deliberately elsewhere to prove env var wins.
    monkeypatch.chdir(tmp_path.parent)

    ctx = build_context(env={ENV_ROOT: str(tmp_path)})

    assert ctx.root == tmp_path.resolve()
    assert ctx.wiki_dir == (tmp_path / "wiki").resolve()


def test_build_context_honors_env_wiki_dir_override(tmp_path: Path) -> None:
    _make_vault(tmp_path)
    (tmp_path / "alt-wiki").mkdir()

    ctx = build_context(tmp_path, env={ENV_WIKI_DIR: "alt-wiki"})

    assert ctx.wiki_dir == (tmp_path / "alt-wiki").resolve()


def test_build_context_defaults_root_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_vault(tmp_path)
    monkeypatch.chdir(tmp_path)

    ctx = build_context(env={})

    assert ctx.root == tmp_path.resolve()


def test_build_context_missing_schema_raises_file_not_found(tmp_path: Path) -> None:
    # Vault dirs but no schema.toml.
    (tmp_path / ".ai-research").mkdir()

    with pytest.raises(FileNotFoundError, match="schema"):
        build_context(tmp_path, env={})


def test_build_context_corrupt_state_raises_value_error(tmp_path: Path) -> None:
    _make_vault(tmp_path, with_state=False)
    (tmp_path / ".ai-research" / "state.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="state"):
        build_context(tmp_path, env={})


def test_server_context_is_frozen(tmp_path: Path) -> None:
    _make_vault(tmp_path)
    ctx = build_context(tmp_path, env={})

    with pytest.raises(FrozenInstanceError):
        ctx.root = tmp_path  # type: ignore[misc]


def test_get_context_raises_before_set() -> None:
    with pytest.raises(RuntimeError, match="not initialized"):
        get_context()


def test_set_and_get_context_roundtrip(tmp_path: Path) -> None:
    _make_vault(tmp_path)
    ctx = build_context(tmp_path, env={})

    set_context(ctx)

    assert get_context() is ctx
