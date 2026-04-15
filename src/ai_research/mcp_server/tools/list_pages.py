"""`list_pages` MCP tool — structured view of `.ai-research/index.md`.

Parses the one-line-per-page retrieval index produced by
``ai_research.wiki.index_rebuild`` and returns it as a JSON-serialisable
list so MCP clients can shortlist pages without re-deriving the index.
No LLM call, no state mutation. Read-only.

Index line format (see :func:`ai_research.wiki.index_rebuild._render`)::

    <relpath> · [INVALID] · title: <t> · tags: <csv> · h1: <a; b> · links:<n> · <summary>

Story 06.2-003.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mcp.types as mcp_types

from ai_research.mcp_server.context import get_context

__all__ = ["TOOL", "handle", "parse_index", "register"]

_SEP = " · "

TOOL = mcp_types.Tool(
    name="list_pages",
    description=(
        "Return the wiki retrieval index as structured JSON: one entry per "
        "page with title, tags, summary, H1 outline, and outbound link count. "
        "Read-only; no LLM call."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "wiki_dir": {
                "type": "string",
                "description": (
                    "Override the vault root's wiki directory; when set, the "
                    "index is looked up at <wiki_dir>/../.ai-research/index.md."
                ),
            },
            "index_path": {
                "type": "string",
                "description": (
                    "Explicit path to an index.md file. Takes precedence over "
                    "`wiki_dir` and the server context default."
                ),
            },
        },
    },
)


def _resolve_index_path(arguments: dict[str, Any]) -> Path:
    """Pick the index.md path: explicit > wiki_dir-derived > server context."""
    explicit = arguments.get("index_path")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit).expanduser()

    wiki_dir = arguments.get("wiki_dir")
    if isinstance(wiki_dir, str) and wiki_dir.strip():
        # `wiki_dir` is typically <root>/wiki; the index lives at
        # <root>/.ai-research/index.md.
        return Path(wiki_dir).expanduser().parent / ".ai-research" / "index.md"

    return get_context().index_path


def parse_index(text: str) -> list[dict[str, Any]]:
    """Parse the on-disk ``index.md`` text into a list of page records.

    Each record has keys ``page``, ``title``, ``tags``, ``summary``,
    ``h1s``, ``outbound_links``, and ``invalid``. Unknown / malformed
    lines are skipped silently — the index is regenerable, so defensive
    parsing is preferred over hard failure.
    """
    pages: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split(_SEP)
        if not parts:
            continue

        page = parts[0].strip()
        if not page:
            continue

        invalid = False
        idx = 1
        if idx < len(parts) and parts[idx].strip() == "[INVALID]":
            invalid = True
            idx += 1

        title = ""
        tags: list[str] = []
        h1s: list[str] = []
        outbound = 0
        summary = ""

        while idx < len(parts):
            field = parts[idx]
            if field.startswith("title: "):
                title = field[len("title: ") :].strip()
            elif field.startswith("tags: "):
                raw_tags = field[len("tags: ") :].strip()
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            elif field.startswith("h1: "):
                raw_h1 = field[len("h1: ") :].strip()
                h1s = [h.strip() for h in raw_h1.split(";") if h.strip()]
            elif field.startswith("links:"):
                try:
                    outbound = int(field[len("links:") :].strip())
                except ValueError:
                    outbound = 0
            else:
                # Unlabelled trailing segment is the summary. Joining any
                # further segments keeps stray `·` inside a summary intact
                # (defensive — `_render` collapses newlines but not `·`).
                summary = _SEP.join(parts[idx:]).strip()
                break
            idx += 1

        pages.append(
            {
                "page": page,
                "title": title,
                "tags": tags,
                "summary": summary,
                "h1s": h1s,
                "outbound_links": outbound,
                "invalid": invalid,
            }
        )
    return pages


async def handle(arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a `list_pages` tool call.

    Args:
        arguments: MCP tool call arguments. Optional keys: ``index_path``
            (explicit file), ``wiki_dir`` (derive index path from vault).
            When neither is provided the handler falls back to the shared
            :class:`ServerContext` initialised at server startup.

    Returns:
        ``{"pages": [ {page, title, tags, summary, h1s, outbound_links, invalid}, ... ]}``.
        An empty index yields ``{"pages": []}`` — not an error.

    Raises:
        FileNotFoundError: if the resolved ``index.md`` does not exist.
    """
    index_path = _resolve_index_path(arguments)
    if not index_path.exists():
        raise FileNotFoundError(f"index.md not found: {index_path}")

    text = index_path.read_text(encoding="utf-8")
    return {"pages": parse_index(text)}


def register(registry: dict[str, Any]) -> None:
    """Add this tool's definition + handler to the server-level registry."""
    registry[TOOL.name] = {"tool": TOOL, "handle": handle}
