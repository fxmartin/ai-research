"""Read-only guarantee — Story 06.3-002.

Exercise every MCP tool handler against a fixture vault and assert that
nothing under ``wiki/``, ``.ai-research/``, or ``sources/`` changes:
same set of files, same bytes, same mtimes.

The `ask` tool normally shells out to ``claude -p "/ask ..."``; we inject
a stub runner via ``ask_tool.set_runner`` so this test never spawns the
real LLM.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ai_research.mcp_server import context as ctx_module
from ai_research.mcp_server.tools import ask as ask_tool
from ai_research.mcp_server.tools import get_page as get_page_tool
from ai_research.mcp_server.tools import list_pages as list_pages_tool
from ai_research.mcp_server.tools import search as search_tool


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _snapshot(root: Path) -> dict[str, tuple[str, int]]:
    """Map every file under ``root`` to ``(sha256, mtime_ns)``."""
    snap: dict[str, tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        mtime_ns = path.stat().st_mtime_ns
        snap[rel] = (digest, mtime_ns)
    return snap


@pytest.fixture
def readonly_vault(tmp_path: Path) -> Path:
    """Minimal vault: wiki/, .ai-research/ (with index.md), and sources/."""
    root = tmp_path / "vault"
    wiki = root / "wiki"
    concepts = wiki / "concepts"
    meta = root / ".ai-research"
    sources = root / "sources" / "2026" / "04"
    concepts.mkdir(parents=True)
    meta.mkdir()
    sources.mkdir(parents=True)

    (wiki / "attention.md").write_text(
        "---\ntitle: Attention\ntags: [ml]\n---\n# Attention\n\nSelf-attention.\n",
        encoding="utf-8",
    )
    (wiki / "transformers.md").write_text(
        "---\ntitle: Transformers\ntags: [ml]\n---\n# Transformers\n\n[[attention]] stack.\n",
        encoding="utf-8",
    )
    (concepts / "embedding.md").write_text(
        "---\ntitle: Embedding\nstub: true\n---\n# Embedding\n\nStub.\n",
        encoding="utf-8",
    )

    (meta / "schema.toml").write_text('[wiki]\nname = "test"\nversion = 1\n', encoding="utf-8")
    (meta / "state.json").write_text("{}\n", encoding="utf-8")
    index_lines = [
        "wiki/attention.md · title: Attention · tags: ml · h1: Attention · links:0 · self-attn",
        "wiki/transformers.md · title: Transformers · tags: ml · h1: Transformers · links:1 · stk",
        "wiki/concepts/embedding.md · title: Embedding · tags:  · h1: Embedding · links:0 · stub",
    ]
    (meta / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    # A plausible source archive file — never touched by MCP tools.
    (sources / "deadbeef-paper.pdf").write_bytes(b"%PDF-fake\n")

    return root


@pytest.fixture(autouse=True)
def _reset_mcp_state() -> Any:
    yield
    ask_tool.reset_runner()
    ctx_module.clear_context()


def _install_ask_stub() -> None:
    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        return json.dumps(
            {
                "answer": "See [[attention]] and [[transformers]].",
                "citations": ["attention", "transformers"],
                "confidence": 0.6,
            }
        )

    ask_tool.set_runner(runner)


def _exercise_all_tools(root: Path) -> None:
    """Invoke every MCP tool handler with valid inputs against ``root``."""
    wiki_dir = str(root / "wiki")

    # search — rg over wiki/
    _run(search_tool.handle({"query": "attention", "wiki_dir": wiki_dir}))

    # list_pages — parse .ai-research/index.md
    _run(list_pages_tool.handle({"index_path": str(root / ".ai-research" / "index.md")}))

    # get_page — plain slug + concepts/ fallback + frontmatter strip
    _run(get_page_tool.handle({"slug": "attention", "wiki_dir": wiki_dir}))
    _run(get_page_tool.handle({"slug": "transformers", "wiki_dir": wiki_dir}))
    _run(
        get_page_tool.handle(
            {
                "slug": "embedding",
                "wiki_dir": wiki_dir,
                "include_frontmatter": False,
            }
        )
    )

    # ask — stubbed runner; no real subprocess.
    _install_ask_stub()
    _run(ask_tool.handle({"question": "What is attention?", "wiki_dir": wiki_dir}))


def test_no_writes_to_vault_after_exercising_all_tools(readonly_vault: Path) -> None:
    """Every file under wiki/, .ai-research/, sources/ is byte-identical after tool calls."""
    before = _snapshot(readonly_vault)
    assert before, "fixture vault unexpectedly empty"

    _exercise_all_tools(readonly_vault)

    after = _snapshot(readonly_vault)

    # Same file set — no tool created, renamed, or deleted anything.
    assert set(before.keys()) == set(after.keys()), (
        f"File set changed.\n"
        f"  added: {sorted(set(after) - set(before))}\n"
        f"  removed: {sorted(set(before) - set(after))}"
    )

    # Byte-identical content.
    for rel, (pre_digest, _pre_mtime) in before.items():
        post_digest, _post_mtime = after[rel]
        assert pre_digest == post_digest, f"Content changed for {rel}"

    # No mtime bumps — caches or counters would surface here too.
    for rel, (_pre_digest, pre_mtime) in before.items():
        _post_digest, post_mtime = after[rel]
        assert pre_mtime == post_mtime, f"mtime changed for {rel}"


def test_get_page_path_traversal_rejected_without_writes(readonly_vault: Path) -> None:
    """Fuzzed / adversarial slugs must be rejected AND leave the vault unchanged."""
    before = _snapshot(readonly_vault)
    wiki_dir = str(readonly_vault / "wiki")

    hostile_slugs: list[Any] = [
        "../etc/passwd",
        "..",
        "/etc/passwd",
        "wiki/attention",  # path separator not allowed
        "Attention",  # uppercase rejected by slug regex
        "-leading-dash",
        "with space",
        "with.dot",
        "",
        None,  # wrong type
        123,  # wrong type
    ]
    for slug in hostile_slugs:
        with pytest.raises((ValueError, FileNotFoundError)):
            _run(get_page_tool.handle({"slug": slug, "wiki_dir": wiki_dir}))

    after = _snapshot(readonly_vault)
    assert before == after, "Vault mutated during path-traversal probing"


def test_ask_error_paths_do_not_write(readonly_vault: Path) -> None:
    """Failure modes in `ask` (empty question, missing index) must not write."""
    before = _snapshot(readonly_vault)
    wiki_dir = str(readonly_vault / "wiki")

    _install_ask_stub()
    with pytest.raises(ValueError):
        _run(ask_tool.handle({"question": "   ", "wiki_dir": wiki_dir}))

    # Missing wiki_dir.
    with pytest.raises(FileNotFoundError):
        _run(ask_tool.handle({"question": "q", "wiki_dir": str(readonly_vault / "nope")}))

    after = _snapshot(readonly_vault)
    assert before == after, "Vault mutated during ask error-path probing"
