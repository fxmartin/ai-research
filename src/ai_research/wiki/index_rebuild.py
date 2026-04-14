"""Regenerate ``.ai-research/index.md`` from the wiki vault (Story 02.2-001).

The index is the deterministic retrieval surface consumed by ``/ask``: one
line per page containing just enough metadata (title, tags, H1 outline,
outbound-link count, one-line summary) to shortlist candidates without
loading the full markdown. It is regenerated wholesale on every call —
cheap, byte-deterministic, and avoids stale-entry drift.

Design notes
------------
- Pure file I/O; no LLM calls. Safe to run from hooks or cron.
- Crash-safe via :func:`ai_research.state.atomic_write`.
- Broken frontmatter is non-fatal: the page is emitted with an
  ``[INVALID]`` marker so the vault keeps indexing cleanly.
- Output is sorted by POSIX relative path so two consecutive rebuilds on an
  unchanged vault diff to zero bytes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from ai_research.state import atomic_write

__all__ = ["IndexEntry", "rebuild_index"]


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
# Match Obsidian wikilinks: [[Target]] or [[Target|Alias]]. We count occurrences,
# including duplicates — repeated references are meaningful signal for retrieval.
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n|]+)(?:\|[^\[\]\n]*)?\]\]")


@dataclass(frozen=True)
class IndexEntry:
    """One line in ``index.md``.

    Attributes:
        path: Absolute path to the page on disk.
        relative_path: Path relative to the wiki root (POSIX form, used for
            sorting and for the emitted line prefix).
        title: Page title — frontmatter ``title``, else first H1, else stem.
        tags: Frontmatter ``tags`` (list of strings). Empty if absent.
        summary: Frontmatter ``summary`` (single line). Empty if absent.
        h1s: Every H1 heading in body order.
        outbound_links: Count of ``[[wikilink]]`` occurrences in the body.
        invalid: True when the frontmatter block failed to parse.
    """

    path: Path
    relative_path: Path
    title: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    h1s: list[str] = field(default_factory=list)
    outbound_links: int = 0
    invalid: bool = False


def rebuild_index(*, wiki_dir: Path, index_path: Path) -> list[IndexEntry]:
    """Scan ``wiki_dir`` and write a one-line-per-page index to ``index_path``.

    Args:
        wiki_dir: Root of the Obsidian-compatible wiki vault. Must exist.
        index_path: Destination path for the generated index (typically
            ``.ai-research/index.md``). Parent directories are created as
            needed; the write is atomic.

    Returns:
        The :class:`IndexEntry` list in the same order they appear in the
        output file (sorted by POSIX relative path).

    Raises:
        FileNotFoundError: ``wiki_dir`` does not exist.
    """
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.exists():
        raise FileNotFoundError(f"wiki_dir not found: {wiki_dir}")

    md_files = sorted(
        (
            p
            for p in wiki_dir.rglob("*.md")
            # Skip dotfiles anywhere in the relative path (e.g. .obsidian/).
            if not any(part.startswith(".") for part in p.relative_to(wiki_dir).parts)
        ),
        key=lambda p: p.relative_to(wiki_dir).as_posix(),
    )

    entries = [_build_entry(p, wiki_dir) for p in md_files]
    payload = _render(entries).encode("utf-8")
    atomic_write(Path(index_path), payload)
    return entries


def _build_entry(page: Path, wiki_dir: Path) -> IndexEntry:
    """Parse a single markdown page into an :class:`IndexEntry`."""
    rel = Path(page.relative_to(wiki_dir).as_posix())
    raw = page.read_text(encoding="utf-8")

    try:
        post = frontmatter.loads(raw)
    except Exception:  # noqa: BLE001 — any frontmatter parse failure is non-fatal.
        return IndexEntry(
            path=page,
            relative_path=rel,
            title=page.stem,
            invalid=True,
        )

    body = post.content
    h1s = [m.group(1).strip() for m in _H1_RE.finditer(body)]

    fm_title = post.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        title = fm_title.strip()
    elif h1s:
        title = h1s[0]
    else:
        title = page.stem

    tags_value = post.get("tags")
    tags: list[str] = []
    if isinstance(tags_value, list):
        tags = [str(t).strip() for t in tags_value if str(t).strip()]
    elif isinstance(tags_value, str) and tags_value.strip():
        tags = [tags_value.strip()]

    summary_value = post.get("summary")
    summary = summary_value.strip() if isinstance(summary_value, str) else ""
    # Keep the index to one line per page — collapse any stray newlines.
    summary = " ".join(summary.split())

    outbound = len(_WIKILINK_RE.findall(body))

    return IndexEntry(
        path=page,
        relative_path=rel,
        title=title,
        tags=tags,
        summary=summary,
        h1s=h1s,
        outbound_links=outbound,
    )


def _render(entries: list[IndexEntry]) -> str:
    """Render entries to the ``index.md`` on-disk format.

    Format per line (pipe-free so grep/awk stays painless)::

        <relpath> · [INVALID] · title: <title> · tags: <csv> · h1: <a; b> · links:<n> · <summary>

    The ``[INVALID]`` marker only appears for pages whose frontmatter failed
    to parse; other fields still best-effort from the filename.
    """
    lines: list[str] = []
    for e in entries:
        parts = [e.relative_path.as_posix()]
        if e.invalid:
            parts.append("[INVALID]")
        parts.append(f"title: {e.title}")
        parts.append(f"tags: {', '.join(e.tags)}")
        parts.append(f"h1: {'; '.join(e.h1s)}")
        parts.append(f"links:{e.outbound_links}")
        parts.append(e.summary)
        lines.append(" · ".join(parts))
    return "\n".join(lines) + ("\n" if lines else "")
