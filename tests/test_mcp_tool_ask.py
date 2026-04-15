"""Tests for the `ask` MCP tool (Story 06.2-001).

The tool is a wrapper around ``claude -p "/ask ..." --output-format json``.
Tests inject a deterministic runner so we never spawn the real LLM.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
import pytest

from ai_research.mcp_server import context as ctx_module
from ai_research.mcp_server import server as server_module
from ai_research.mcp_server.tools import ask as ask_tool

# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fixture_vault(tmp_path: Path) -> Path:
    """A minimal vault root: wiki/ with 3 pages + .ai-research/index.md."""
    root = tmp_path / "vault"
    wiki = root / "wiki"
    meta = root / ".ai-research"
    wiki.mkdir(parents=True)
    meta.mkdir()

    (wiki / "attention.md").write_text(
        "# Attention\n\nAttention is all you need.\n", encoding="utf-8"
    )
    (wiki / "transformers.md").write_text(
        "# Transformers\n\nArchitecture built on attention.\n", encoding="utf-8"
    )
    (wiki / "embeddings.md").write_text(
        "# Embeddings\n\nVector representations.\n", encoding="utf-8"
    )
    (meta / "index.md").write_text(
        "attention · ml · Self-attention mechanism · Attention · 1\n"
        "transformers · ml · Encoder-decoder stack · Transformers · 2\n"
        "embeddings · ml · Vector representations · Embeddings · 0\n",
        encoding="utf-8",
    )
    # Minimal schema + state for ServerContext bootstrap.
    (meta / "schema.toml").write_text('[wiki]\nname = "test"\nversion = 1\n', encoding="utf-8")
    return root


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _install_stub_runner(payload: dict[str, Any]) -> None:
    """Swap in a runner that returns the given payload as JSON."""

    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        return json.dumps(payload)

    ask_tool.set_runner(runner)


@pytest.fixture(autouse=True)
def _reset_runner_between_tests() -> Any:
    yield
    ask_tool.reset_runner()
    ctx_module.clear_context()


# --- Tests ------------------------------------------------------------------


def test_ask_tool_registered_in_list_tools() -> None:
    """`ask` must appear in the server's tool list with the right schema."""
    srv = server_module.build_server()

    async def call() -> list[mcp_types.Tool]:
        req = mcp_types.ListToolsRequest(method="tools/list")
        handler = srv.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(req)
        return result.root.tools  # type: ignore[attr-defined,no-any-return]

    tools = _run(call())
    names = [t.name for t in tools]
    assert "ask" in names
    ask_def = next(t for t in tools if t.name == "ask")
    assert "question" in ask_def.inputSchema["properties"]
    assert "limit" in ask_def.inputSchema["properties"]
    assert "wiki_dir" in ask_def.inputSchema["properties"]
    assert ask_def.inputSchema["required"] == ["question"]


def test_ask_happy_path_returns_contract_shape(fixture_vault: Path) -> None:
    """Valid question → {answer, citations, confidence} with resolving citations."""
    _install_stub_runner(
        {
            "answer": "Attention is central [[attention]] to [[transformers]].",
            "citations": ["attention", "transformers"],
            "confidence": 0.7,
        }
    )
    result = _run(
        ask_tool.handle(
            {
                "question": "What is attention?",
                "wiki_dir": str(fixture_vault / "wiki"),
            }
        )
    )
    assert set(result.keys()) == {"answer", "citations", "confidence"}
    assert result["answer"]
    assert set(result["citations"]) == {"attention", "transformers"}
    assert 0.0 <= result["confidence"] < 1.0
    # Every returned citation must exist as an actual page.
    wiki = fixture_vault / "wiki"
    for slug in result["citations"]:
        assert (wiki / f"{slug}.md").exists()


def test_ask_empty_question_raises(fixture_vault: Path) -> None:
    with pytest.raises(ValueError, match="question"):
        _run(ask_tool.handle({"question": "", "wiki_dir": str(fixture_vault / "wiki")}))


def test_ask_whitespace_question_raises(fixture_vault: Path) -> None:
    with pytest.raises(ValueError, match="question"):
        _run(ask_tool.handle({"question": "   ", "wiki_dir": str(fixture_vault / "wiki")}))


def test_ask_missing_index_raises(tmp_path: Path) -> None:
    """No .ai-research/index.md → clean FileNotFoundError."""
    root = tmp_path / "bare"
    wiki = root / "wiki"
    wiki.mkdir(parents=True)
    _install_stub_runner({"answer": "x", "citations": [], "confidence": 0.0})
    with pytest.raises(FileNotFoundError, match="index.md"):
        _run(ask_tool.handle({"question": "anything", "wiki_dir": str(wiki)}))


def test_ask_missing_wiki_dir_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-wiki"
    with pytest.raises(FileNotFoundError):
        _run(ask_tool.handle({"question": "anything", "wiki_dir": str(missing)}))


def test_ask_broken_citation_raises(fixture_vault: Path) -> None:
    """Citations that don't resolve to vault pages → RuntimeError."""
    _install_stub_runner(
        {
            "answer": "This cites a phantom [[hallucinated-page]].",
            "citations": ["hallucinated-page"],
            "confidence": 0.3,
        }
    )
    with pytest.raises(RuntimeError, match="unresolved citations"):
        _run(
            ask_tool.handle(
                {
                    "question": "What is attention?",
                    "wiki_dir": str(fixture_vault / "wiki"),
                }
            )
        )


def test_ask_invalid_contract_raises(fixture_vault: Path) -> None:
    """Missing required keys → RuntimeError about AskResponse contract."""

    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        # Has keys the extractor recognizes, but violates AskResponse
        # (confidence must be float in [0, 1); 1.5 fails validation).
        return json.dumps({"answer": "hi", "citations": [], "confidence": 1.5})

    ask_tool.set_runner(runner)
    with pytest.raises(RuntimeError, match="AskResponse"):
        _run(
            ask_tool.handle(
                {
                    "question": "What is attention?",
                    "wiki_dir": str(fixture_vault / "wiki"),
                }
            )
        )


def test_ask_accepts_claude_envelope(fixture_vault: Path) -> None:
    """`claude -p --output-format json` wraps output in a `result` envelope."""
    inner = {
        "answer": "See [[attention]].",
        "citations": ["attention"],
        "confidence": 0.4,
    }
    envelope = {"type": "result", "result": json.dumps(inner)}

    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        return json.dumps(envelope)

    ask_tool.set_runner(runner)
    result = _run(
        ask_tool.handle(
            {
                "question": "What is attention?",
                "wiki_dir": str(fixture_vault / "wiki"),
            }
        )
    )
    assert result["citations"] == ["attention"]


def test_ask_empty_stdout_raises(fixture_vault: Path) -> None:
    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        return ""

    ask_tool.set_runner(runner)
    with pytest.raises(RuntimeError, match="empty stdout"):
        _run(
            ask_tool.handle(
                {
                    "question": "anything",
                    "wiki_dir": str(fixture_vault / "wiki"),
                }
            )
        )


def test_ask_forwards_limit_to_runner(fixture_vault: Path) -> None:
    """Optional `limit` argument is threaded through to the runner."""
    seen: dict[str, Any] = {}

    def runner(question: str, *, cwd: Path, limit: int | None) -> str:
        seen["limit"] = limit
        seen["question"] = question
        seen["cwd"] = cwd
        return json.dumps(
            {"answer": "ok [[attention]]", "citations": ["attention"], "confidence": 0.5}
        )

    ask_tool.set_runner(runner)
    _run(
        ask_tool.handle(
            {
                "question": "What is attention?",
                "limit": 3,
                "wiki_dir": str(fixture_vault / "wiki"),
            }
        )
    )
    assert seen["limit"] == 3
    assert seen["question"] == "What is attention?"
    # cwd should be the vault root (parent of wiki/).
    assert seen["cwd"] == (fixture_vault / "wiki").parent


def test_ask_uses_server_context_when_no_override(fixture_vault: Path) -> None:
    """With no `wiki_dir` override, falls back to installed ServerContext."""
    ctx = ctx_module.build_context(root=fixture_vault)
    ctx_module.set_context(ctx)
    _install_stub_runner(
        {"answer": "ok [[attention]]", "citations": ["attention"], "confidence": 0.5}
    )
    result = _run(ask_tool.handle({"question": "What is attention?"}))
    assert result["citations"] == ["attention"]
