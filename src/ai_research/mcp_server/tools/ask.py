"""`ask` MCP tool — Q&A with citations over the ai-research wiki.

Thin wrapper around the existing ``/ask`` slash command (Story 03.3-001).
Because v1 is Claude Code-native (no Anthropic SDK in the toolkit), this
tool shells out to ``claude -p "/ask '<question>'" --output-format json``
from the vault root, then:

1. Parses the JSON with :class:`ai_research.wiki.ask.AskResponse` to
   enforce the ``{answer, citations, confidence}`` contract.
2. Validates every citation resolves to a real page via
   :func:`ai_research.wiki.ask.check_citations`.
3. Returns a JSON-serialisable dict.

The tool is strictly read-only. No state mutation, no disk writes.

Story 06.2-001.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import mcp.types as mcp_types

from ai_research.mcp_server.context import get_context
from ai_research.wiki.ask import AskResponse, check_citations

__all__ = ["ASK_TIMEOUT_SECONDS", "TOOL", "AskRunner", "handle", "register", "run_claude_ask"]

# Hard ceiling on a single `claude -p /ask` invocation. The two-stage retrieval
# (shortlist + read shortlisted pages + synthesize) should comfortably finish
# well under this; anything longer is almost certainly a hung subprocess and
# we would rather fail the MCP request cleanly than block the stdio loop.
ASK_TIMEOUT_SECONDS = 180.0


TOOL = mcp_types.Tool(
    name="ask",
    description=(
        "Answer a natural-language question from the ai-research wiki using the "
        "same two-stage retrieval as the /ask slash command (index.md shortlist "
        "→ read shortlisted pages → synthesize). Returns {answer, citations, "
        "confidence}. Read-only."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural-language question to answer from the wiki.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 8,
                "description": (
                    "Maximum number of pages to include in the shortlist "
                    "(default 8, matching /ask's protocol)."
                ),
            },
            "wiki_dir": {
                "type": "string",
                "description": (
                    "Override the wiki directory. Defaults to the server "
                    "context's resolved wiki path."
                ),
            },
        },
        "required": ["question"],
    },
)


class AskRunner(Protocol):
    """Callable that executes an ``/ask`` invocation and returns JSON text.

    Implementations must return stdout of ``claude -p "/ask ..." --output-format json``
    as a raw string. Separated from :func:`handle` so tests can inject a
    deterministic stub without spawning real LLM subprocesses.
    """

    def __call__(self, question: str, *, cwd: Path, limit: int | None) -> str:  # pragma: no cover
        ...


def run_claude_ask(question: str, *, cwd: Path, limit: int | None) -> str:
    """Default runner — shells out to ``claude -p "/ask ..." --output-format json``.

    Args:
        question: The user's question, forwarded verbatim to ``/ask``.
        cwd: Working directory for the subprocess (the vault root).
        limit: Optional shortlist limit appended as a hint; the slash command
            already caps at 8, so this is advisory.

    Returns:
        Raw stdout (JSON text) from the ``claude`` subprocess.

    Raises:
        RuntimeError: If the ``claude`` CLI is missing or returns non-zero.
    """
    hint = f" (limit shortlist to {limit} pages)" if limit else ""
    prompt = f"/ask {question}{hint}"
    try:
        completed = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=ASK_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "`claude` CLI not found on PATH; the ask tool requires Claude Code "
            "to be installed to run the /ask slash command."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills the child on timeout, but be explicit about the
        # error surfaced to the MCP client so a hung /ask doesn't masquerade
        # as a generic runtime failure.
        raise RuntimeError(
            f"`claude -p /ask` timed out after {ASK_TIMEOUT_SECONDS:.0f}s; "
            "subprocess was terminated."
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            f"`claude -p /ask` exited with status {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout


_runner: AskRunner = run_claude_ask


def _set_runner(runner: AskRunner) -> None:
    """Test-only hook to swap the default subprocess runner."""
    global _runner
    _runner = runner


def _reset_runner() -> None:
    """Test-only hook to restore the default runner."""
    global _runner
    _runner = run_claude_ask


def _resolve_paths(override: str | None) -> tuple[Path, Path]:
    """Return ``(vault_root, wiki_dir)``.

    Prefers the per-call ``wiki_dir`` override; falls back to the
    :class:`ServerContext` singleton installed at startup (06.1-002).
    """
    if override:
        wiki_dir = Path(override).expanduser().resolve()
        # Assume the vault root is the parent when an override is provided;
        # this is how /ask is invoked from a repo cwd.
        return wiki_dir.parent, wiki_dir
    ctx = get_context()
    return ctx.root, ctx.wiki_dir


def _extract_ask_payload(raw_stdout: str) -> dict[str, Any]:
    """Pull the ``/ask`` JSON object out of ``claude -p --output-format json``.

    Claude Code's JSON envelope wraps the assistant's final message. The
    final message itself must be the ``/ask`` JSON object (per the slash
    command spec). We accept either:

    1. The raw ``/ask`` payload (direct JSON on stdout, no envelope).
    2. Claude Code's envelope where the inner payload is under ``result``
       or inside the last assistant ``content`` block.
    """
    text = raw_stdout.strip()
    if not text:
        raise RuntimeError("/ask returned empty stdout")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"/ask stdout was not valid JSON: {exc}") from exc

    # Case 1: raw /ask payload.
    if isinstance(parsed, dict) and "answer" in parsed and "citations" in parsed:
        return parsed

    # Case 2: Claude Code envelope with a `result` string.
    if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
        try:
            inner = json.loads(parsed["result"])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"/ask envelope 'result' was not valid JSON: {exc}") from exc
        if isinstance(inner, dict) and "answer" in inner and "citations" in inner:
            return inner

    raise RuntimeError(
        "Could not locate an /ask JSON payload in claude -p stdout; "
        "expected keys {answer, citations, confidence}."
    )


async def handle(arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute an ``ask`` tool call.

    Args:
        arguments: MCP tool call arguments. Requires ``question`` (non-empty
            string). Optional ``limit`` (int, 1–8) and ``wiki_dir`` (string
            path override).

    Returns:
        ``{answer, citations, confidence}`` — the ``/ask`` contract, with
        ``citations`` guaranteed to resolve to vault pages.

    Raises:
        ValueError: If ``question`` is missing, empty, or whitespace-only.
        FileNotFoundError: If the resolved wiki directory does not exist,
            or ``.ai-research/index.md`` is missing (vault not initialized).
        RuntimeError: If the ``claude`` subprocess fails, the JSON contract
            is violated, or any citation fails resolution.
    """
    raw_question = arguments.get("question", "")
    if not isinstance(raw_question, str) or not raw_question.strip():
        raise ValueError("`question` is required and must be a non-empty string.")

    limit_arg = arguments.get("limit")
    limit: int | None = int(limit_arg) if limit_arg is not None else None

    root, wiki_dir = _resolve_paths(arguments.get("wiki_dir"))
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki directory does not exist: {wiki_dir}")

    index_path = root / ".ai-research" / "index.md"
    if not index_path.is_file():
        raise FileNotFoundError(
            f".ai-research/index.md not found under {root}; run "
            "`ai-research index-rebuild` before querying."
        )

    raw_stdout = _runner(raw_question.strip(), cwd=root, limit=limit)
    payload = _extract_ask_payload(raw_stdout)

    # Enforce the /ask JSON contract.
    try:
        response = AskResponse.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError subclass of Exception
        raise RuntimeError(f"/ask response violated AskResponse contract: {exc}") from exc

    # Enforce citation integrity — every citation must resolve.
    check = check_citations({"citations": response.citations}, wiki_dir=wiki_dir)
    if not check.ok:
        raise RuntimeError(f"/ask returned unresolved citations: {check.broken}")

    return {
        "answer": response.answer,
        "citations": list(response.citations),
        "confidence": response.confidence,
    }


def register(registry: dict[str, Any]) -> None:
    """Add this tool's definition + handler to the server-level registry."""
    registry[TOOL.name] = {"tool": TOOL, "handle": handle}


# Re-exported so tests can swap the subprocess runner without touching globals.
set_runner: Callable[[AskRunner], None] = _set_runner
reset_runner: Callable[[], None] = _reset_runner
