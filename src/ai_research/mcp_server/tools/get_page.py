"""`get_page` MCP tool — full-page fetch by slug.

Returns the full markdown content of a wiki page given its slug. Looks
under ``wiki_dir`` first, then ``wiki_dir/concepts/`` as a fallback for
stub pages. Read-only.

Path-traversal is the one way a read-only tool can still leak data
(e.g. reading ``~/.ssh/config`` via a crafted slug). The slug is
validated against a strict regex (``^[a-z0-9][a-z0-9-]*$``) and the
resolved path is verified to live under the configured wiki directory.

Story 06.2-004.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import frontmatter
import mcp.types as mcp_types

__all__ = ["SLUG_PATTERN", "TOOL", "handle", "register"]

# Plain filename slug: lowercase alphanumerics plus hyphens; must start
# with an alphanumeric. No slashes, no dots, no leading dash.
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

TOOL = mcp_types.Tool(
    name="get_page",
    description=(
        "Fetch the full markdown content of a single wiki page by slug. "
        "Looks under wiki/ first, then wiki/concepts/ as a fallback. "
        "Read-only. Slug must be a plain filename (no path separators)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": (
                    "Page slug, e.g. 'dario-amodei'. Must match "
                    "^[a-z0-9][a-z0-9-]*$ — no path separators."
                ),
            },
            "include_frontmatter": {
                "type": "boolean",
                "description": (
                    "If false, strip the YAML front-matter block before returning. Default true."
                ),
            },
            "wiki_dir": {
                "type": "string",
                "description": (
                    "Override the wiki directory. Defaults to $AI_RESEARCH_ROOT/wiki or ./wiki."
                ),
            },
        },
        "required": ["slug"],
    },
)


def _resolve_wiki_dir(override: str | None) -> Path:
    """Pick the wiki directory: explicit override > env var > cwd."""
    if override:
        return Path(override).expanduser()
    root_env = os.environ.get("AI_RESEARCH_ROOT")
    if root_env:
        return Path(root_env).expanduser() / "wiki"
    return Path.cwd() / "wiki"


def _validate_slug(slug: Any) -> str:
    """Ensure ``slug`` is a safe plain-filename string.

    Raises:
        ValueError: if the slug is missing, not a string, empty, or
            contains characters outside the safe regex.
    """
    if not isinstance(slug, str) or not slug:
        raise ValueError("`slug` is required and must be a non-empty string.")
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            f"Invalid `slug` {slug!r}: must match {SLUG_PATTERN.pattern} "
            "(lowercase alphanumerics and hyphens only, no path separators)."
        )
    return slug


def _resolve_page_path(wiki_dir: Path, slug: str) -> Path:
    """Find the page file for ``slug``, or raise ``FileNotFoundError``.

    Looks up ``wiki_dir/<slug>.md`` first, then
    ``wiki_dir/concepts/<slug>.md``. Also defensively verifies the
    resolved path sits inside ``wiki_dir`` to catch any symlink shenanigans.
    """
    if not wiki_dir.exists() or not wiki_dir.is_dir():
        raise FileNotFoundError(f"Wiki directory not found: {wiki_dir}")

    wiki_resolved = wiki_dir.resolve()
    candidates = [
        wiki_dir / f"{slug}.md",
        wiki_dir / "concepts" / f"{slug}.md",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        # Defence-in-depth: the resolved target must live under wiki_dir.
        try:
            resolved.relative_to(wiki_resolved)
        except ValueError as exc:
            raise ValueError(f"Resolved page path for slug {slug!r} escapes wiki_dir.") from exc
        return resolved

    raise FileNotFoundError(f"No page found for slug {slug!r} under {wiki_dir}")


def _relative_display_path(page_path: Path, wiki_dir: Path) -> str:
    """Render the page path relative to the vault root (parent of wiki_dir)."""
    wiki_resolved = wiki_dir.resolve()
    vault_root = wiki_resolved.parent
    try:
        rel = page_path.resolve().relative_to(vault_root)
    except ValueError:
        # Fallback: show path relative to wiki_dir itself.
        rel = page_path.resolve().relative_to(wiki_resolved)
        return f"{wiki_resolved.name}/{rel.as_posix()}"
    return rel.as_posix()


async def handle(arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a `get_page` tool call.

    Args:
        arguments: MCP tool call arguments. Must contain ``slug``; may
            contain ``include_frontmatter`` (bool, default True) and
            ``wiki_dir`` (str path override).

    Returns:
        ``{slug, path, content}`` — path is relative to the vault root
        (parent of wiki_dir); content is the full markdown text
        (optionally with front-matter stripped).

    Raises:
        ValueError: If ``slug`` is missing, empty, or fails validation.
        FileNotFoundError: If the wiki directory or the page does not exist.
    """
    slug = _validate_slug(arguments.get("slug"))

    include_frontmatter = arguments.get("include_frontmatter", True)
    if not isinstance(include_frontmatter, bool):
        raise ValueError("`include_frontmatter` must be a boolean if provided.")

    wiki_dir = _resolve_wiki_dir(arguments.get("wiki_dir"))
    page_path = _resolve_page_path(wiki_dir, slug)
    raw = page_path.read_text(encoding="utf-8")

    if include_frontmatter:
        content = raw
    else:
        post = frontmatter.loads(raw)
        content = post.content

    return {
        "slug": slug,
        "path": _relative_display_path(page_path, wiki_dir),
        "content": content,
    }


def register(registry: dict[str, Any]) -> None:
    """Add this tool's definition + handler to the server-level registry."""
    registry[TOOL.name] = {"tool": TOOL, "handle": handle}
