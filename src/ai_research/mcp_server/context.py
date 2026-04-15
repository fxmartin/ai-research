"""Shared server bootstrap for the ai-research MCP stdio server.

Story 06.1-002: load ``schema.toml`` and ``state.json`` once at startup and
resolve the vault root so every tool handler (``ask``, ``search``,
``list_pages``, ``get_page``) shares the same in-memory handles without
re-reading disk per call.

The context is intentionally immutable (``frozen=True``). Reload semantics
(SIGHUP, index.md staleness) will be layered on top in subsequent stories by
building a fresh :class:`ServerContext` and swapping the module-level
singleton via :func:`set_context`.

Environment variables
---------------------
``AI_RESEARCH_ROOT``
    Absolute path to the vault root. Overrides the cwd default.
``AI_RESEARCH_WIKI_DIR``
    Name (or relative path under root) of the wiki directory. Default ``wiki``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ai_research.schema import Schema, load_schema
from ai_research.state import State, load_state

__all__ = [
    "ENV_ROOT",
    "ENV_WIKI_DIR",
    "ServerContext",
    "build_context",
    "clear_context",
    "get_context",
    "set_context",
]

ENV_ROOT = "AI_RESEARCH_ROOT"
ENV_WIKI_DIR = "AI_RESEARCH_WIKI_DIR"

_DEFAULT_WIKI_DIR = "wiki"
_META_DIR = ".ai-research"
_SCHEMA_FILE = "schema.toml"
_STATE_FILE = "state.json"
_INDEX_FILE = "index.md"


@dataclass(frozen=True, slots=True)
class ServerContext:
    """Immutable bootstrap handles shared across MCP tool handlers.

    Attributes:
        root: Vault root directory (the repo/project dir containing ``wiki/``
            and ``.ai-research/``).
        wiki_dir: Directory holding materialized markdown pages.
        state_path: Path to ``.ai-research/state.json``.
        schema_path: Path to ``.ai-research/schema.toml``.
        index_path: Path to ``.ai-research/index.md`` (may not yet exist on a
            fresh vault; tools handle absence).
        state: Parsed :class:`State` loaded at bootstrap.
        schema: Parsed :class:`Schema` loaded at bootstrap.
    """

    root: Path
    wiki_dir: Path
    state_path: Path
    schema_path: Path
    index_path: Path
    state: State
    schema: Schema


def _resolve_root(root: Path | str | None, env: dict[str, str]) -> Path:
    """Resolve the vault root honoring an explicit arg, env var, then cwd."""
    if root is not None:
        return Path(root).resolve()
    env_root = env.get(ENV_ROOT)
    if env_root:
        return Path(env_root).resolve()
    return Path.cwd().resolve()


def _resolve_wiki_dir(root: Path, wiki_dir: Path | str | None, env: dict[str, str]) -> Path:
    """Resolve the wiki dir relative to root unless an absolute path is given."""
    if wiki_dir is None:
        wiki_dir = env.get(ENV_WIKI_DIR, _DEFAULT_WIKI_DIR)
    candidate = Path(wiki_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def build_context(
    root: Path | str | None = None,
    *,
    wiki_dir: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> ServerContext:
    """Construct a :class:`ServerContext` from env vars and sensible defaults.

    Args:
        root: Explicit vault root. If ``None``, ``AI_RESEARCH_ROOT`` then cwd.
        wiki_dir: Explicit wiki directory. If ``None``, ``AI_RESEARCH_WIKI_DIR``
            then ``wiki`` relative to root.
        env: Environment mapping (defaults to :data:`os.environ`). Exposed for
            deterministic tests.

    Raises:
        FileNotFoundError: if ``schema.toml`` is missing.
        ValueError: if ``schema.toml`` or ``state.json`` fails to parse.
    """
    env_map = dict(os.environ) if env is None else env
    resolved_root = _resolve_root(root, env_map)
    resolved_wiki = _resolve_wiki_dir(resolved_root, wiki_dir, env_map)

    meta_dir = resolved_root / _META_DIR
    schema_path = meta_dir / _SCHEMA_FILE
    state_path = meta_dir / _STATE_FILE
    index_path = meta_dir / _INDEX_FILE

    schema = load_schema(schema_path)
    # ``load_state`` already returns an empty State() when state.json is
    # absent, which is the correct behaviour for a freshly-initialized vault.
    state = load_state(state_path)

    return ServerContext(
        root=resolved_root,
        wiki_dir=resolved_wiki,
        state_path=state_path,
        schema_path=schema_path,
        index_path=index_path,
        state=state,
        schema=schema,
    )


_context: ServerContext | None = None


def set_context(ctx: ServerContext) -> None:
    """Install ``ctx`` as the module-level singleton used by tool handlers."""
    global _context
    _context = ctx


def get_context() -> ServerContext:
    """Return the active :class:`ServerContext`.

    Raises:
        RuntimeError: if no context has been installed yet. Tool handlers
            should only be invoked after :func:`build_context` + :func:`set_context`
            have run at startup.
    """
    if _context is None:
        raise RuntimeError(
            "MCP server context not initialized; call build_context() "
            "and set_context() before handling tool calls."
        )
    return _context


def clear_context() -> None:
    """Reset the singleton. Test-only hook."""
    global _context
    _context = None
