"""`search` MCP tool — lexical hits over the wiki/ directory.

Thin wrapper around `ai_research.search.run_search` (ripgrep-backed). No
LLM call, no state mutation. Returns structured hits as
`{hits: [{page, line, snippet}, ...]}`.

Story 06.2-002.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mcp.types as mcp_types

from ai_research.search import run_search

__all__ = ["DEFAULT_LIMIT", "TOOL", "handle", "register"]

DEFAULT_LIMIT = 20

TOOL = mcp_types.Tool(
    name="search",
    description=(
        "Lexical (ripgrep) search over the ai-research wiki. Returns a list of "
        "hits with page path, line number, and snippet. No LLM call. Read-only."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Literal or regex pattern passed to ripgrep.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": f"Maximum number of hits to return (default {DEFAULT_LIMIT}).",
            },
            "wiki_dir": {
                "type": "string",
                "description": (
                    "Override the wiki directory. Defaults to $AI_RESEARCH_ROOT/wiki or ./wiki."
                ),
            },
        },
        "required": ["query"],
    },
)


def _resolve_wiki_dir(override: str | None) -> Path:
    """Pick the wiki directory: explicit override > env var > cwd.

    06.1-002 will replace this with a shared `ServerContext`. Until then
    we read env vars lazily so the MCP tool stays self-contained.
    """
    if override:
        return Path(override).expanduser()

    root_env = os.environ.get("AI_RESEARCH_ROOT")
    if root_env:
        return Path(root_env).expanduser() / "wiki"

    return Path.cwd() / "wiki"


async def handle(arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a `search` tool call.

    Args:
        arguments: MCP tool call arguments. Must contain `query`; may
            contain `limit` (int, default 20) and `wiki_dir` (str path
            override).

    Returns:
        `{hits: [{page, line, snippet}, ...]}` — JSON-serialisable dict.

    Raises:
        ValueError: If `query` is missing, empty, or whitespace-only.
        FileNotFoundError: If the resolved wiki directory does not exist.
        RuntimeError: If ripgrep is missing or fails unexpectedly.
    """
    raw_query = arguments.get("query", "")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise ValueError("`query` is required and must be a non-empty string.")

    limit_arg = arguments.get("limit")
    limit = int(limit_arg) if limit_arg is not None else DEFAULT_LIMIT

    wiki_dir = _resolve_wiki_dir(arguments.get("wiki_dir"))

    hits = run_search(raw_query, wiki_dir=wiki_dir, limit=limit)
    return {"hits": [hit.to_dict() for hit in hits]}


def register(registry: dict[str, Any]) -> None:
    """Add this tool's definition + handler to the server-level registry.

    The registry is consumed by the `list_tools` / `call_tool` decorators
    wired in `ai_research.mcp_server.server`.
    """
    registry[TOOL.name] = {"tool": TOOL, "handle": handle}
