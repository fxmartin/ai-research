"""Atomic wiki-page materialization (Story 02.1-001).

The ``materialize`` verb is pure file I/O: it takes an LLM-drafted markdown
body (from a file or stdin) plus an archived source path, stamps standard
YAML frontmatter, and writes ``wiki/<slug>.md`` atomically via
:func:`ai_research.state.atomic_write`. It then records the
``source_hash -> page_path`` mapping in ``state.json`` so subsequent
re-ingests can short-circuit idempotently (Story 02.1-002).

Design notes
------------
- The slug comes from ``title`` frontmatter on the draft, else the first H1
  in the draft body, else the source filename stem. This keeps behavior
  predictable even when the LLM forgets to set a title.
- Our frontmatter keys (``source_hash``, ``ingested_at``, ``source``,
  ``locked``) always override what the draft set — the draft controls
  *content* and editorial metadata (``tags``, ``summary``); the toolkit
  controls provenance.
- ``locked: false`` is written on first materialization only. Story 02.1-002
  handles preserving ``locked: true`` on re-ingest.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import frontmatter

from ai_research.archive import slugify
from ai_research.state import State, atomic_write, load_state, save_state

__all__ = ["MaterializeResult", "materialize"]


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class MaterializeResult:
    """Outcome of a successful ``materialize`` call."""

    page_path: Path
    source_hash: str
    slug: str


def _sha256_of_file(path: Path) -> str:
    """Return hex SHA-256 of ``path`` streamed in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_draft(
    draft_path: Path | None,
    stdin: TextIO | None,
) -> frontmatter.Post:
    """Read the draft as a python-frontmatter ``Post`` from disk or stdin."""
    if draft_path is not None:
        text = Path(draft_path).read_text(encoding="utf-8")
    elif stdin is not None:
        text = stdin.read()
    else:
        raise ValueError("materialize requires either draft_path or stdin to be provided")
    return frontmatter.loads(text)


def _pick_title(post: frontmatter.Post, source: Path) -> str:
    """Pick a title: frontmatter ``title`` > first H1 in body > source stem."""
    fm_title = post.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    match = _H1_RE.search(post.content)
    if match:
        return match.group(1).strip()
    return source.stem


def materialize(
    *,
    source: Path,
    draft_path: Path | None,
    wiki_dir: Path,
    state_path: Path,
    now: datetime | None = None,
    stdin: TextIO | None = None,
) -> MaterializeResult:
    """Write ``wiki/<slug>.md`` from a draft and record state.

    Args:
        source: Path to the archived source file (hashed for ``source_hash``).
        draft_path: Path to the markdown draft produced by the LLM. Exactly
            one of ``draft_path`` / ``stdin`` must be provided.
        wiki_dir: Root of the Obsidian-compatible wiki vault.
        state_path: Path to ``state.json`` (created if missing).
        now: Override wall clock for ``ingested_at`` (tests pass a fixed UTC
            timestamp for deterministic output).
        stdin: Text stream to read the draft from when ``draft_path`` is
            ``None`` — typically ``sys.stdin``.

    Returns:
        :class:`MaterializeResult` with the final page path, source hash,
        and slug used.

    Raises:
        FileNotFoundError: the archived ``source`` does not exist.
        ValueError: neither ``draft_path`` nor ``stdin`` was provided.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"source not found: {source}")

    post = _load_draft(draft_path, stdin)
    title = _pick_title(post, source)
    slug = slugify(title)
    timestamp = (now or datetime.now(tz=UTC)).astimezone(UTC)
    source_hash = _sha256_of_file(source)

    # Toolkit-owned metadata always wins over draft frontmatter.
    post["title"] = title
    post["source"] = str(source)
    post["ingested_at"] = timestamp.isoformat()
    post["source_hash"] = source_hash
    post["locked"] = False

    page_path = Path(wiki_dir) / f"{slug}.md"
    payload = frontmatter.dumps(post).encode("utf-8")
    if not payload.endswith(b"\n"):
        payload += b"\n"

    atomic_write(page_path, payload)

    # Update state.json after the page lands so a crash mid-page-write never
    # leaves state pointing at a non-existent file.
    state: State = load_state(state_path)
    rel_page = _relative_or_absolute(page_path, state_path)
    state.sources[source_hash] = rel_page
    existing = state.pages.get(rel_page, [])
    if source_hash not in existing:
        existing.append(source_hash)
    state.pages[rel_page] = existing
    save_state(state_path, state)

    return MaterializeResult(page_path=page_path, source_hash=source_hash, slug=slug)


def _relative_or_absolute(page_path: Path, state_path: Path) -> str:
    """Return ``page_path`` relative to the project root (state_path's parents).

    We anchor on ``state_path.parent.parent`` (e.g. ``.ai-research``'s parent
    is the repo root). If that fails, fall back to the absolute path string —
    state.json's schema accepts either.
    """
    try:
        root = Path(state_path).resolve().parent.parent
        return str(Path(page_path).resolve().relative_to(root))
    except ValueError:
        return str(Path(page_path).resolve())
