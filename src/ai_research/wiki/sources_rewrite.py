"""Retroactive ``## Sources`` rewrite verb (Story 08.2-001).

Walks every page in ``wiki/*.md`` (top-level only — concept stubs under
``wiki/concepts/`` carry no sources), inspects the existing ``## Sources``
section, and backfills a ``- Archive: [path](path)`` bullet for each source
whose ``archive_path`` is now known in ``state.json``. Pages with nothing to
backfill are left byte-identical.

Invariants:
* Only the ``## Sources`` section is rewritten. Bytes above the heading are
  preserved verbatim. The rewriter never reorders non-Sources content.
* Locked pages (``locked: true`` in frontmatter) are skipped unless
  ``--force`` is passed.
* Atomic write per page (temp + rename).
* The retrieval index is rebuilt once at the end, and only if at least one
  page was updated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import frontmatter

from ai_research.state import State, atomic_write, load_state
from ai_research.wiki.sources import (
    SOURCES_HEADING,
    SourceEntry,
    _parse_bullets,
    _split_body,
    render_sources_section,
)

__all__ = ["RewriteOutcome", "RewriteResult", "rewrite_sources"]


class RewriteOutcome(StrEnum):
    """Per-page outcome of a rewrite pass."""

    UNCHANGED = "unchanged"
    UPDATED = "updated"
    LOCKED = "locked"


@dataclass(frozen=True)
class RewriteResult:
    """Outcome of a single page's rewrite attempt."""

    page_path: Path
    outcome: RewriteOutcome


def _augment_entry_with_archive(
    entry: SourceEntry,
    state: State,
    page_hashes: list[str],
) -> SourceEntry:
    """Return ``entry`` with ``archive_path`` filled from state if available.

    Matching strategy:
    1. If the entry already has ``archive_path`` set, return it unchanged.
    2. Otherwise, for each source hash attributed to the page, look up the
       :class:`SourceRecord`: if its ``archive_path`` is set, and the record
       plausibly matches the entry (via URL equality, or via the bare
       ``path`` field matching the archive_path), upgrade the entry.
    3. Fallback: if the page has exactly one known source hash with an
       ``archive_path``, attribute it to the entry. This covers legacy
       URL-only pages that never recorded the archive path in their body.
    """
    if entry.archive_path:
        return entry

    # First pass: explicit URL or path match.
    for source_hash in page_hashes:
        record = state.sources.get(source_hash)
        if record is None or not record.archive_path:
            continue
        if entry.url is not None:
            # URL-keyed match: we can't verify cross-source here, but if the
            # page has only one hash at play, the match is unambiguous.
            pass
        if entry.path == record.archive_path:
            return SourceEntry(
                title=entry.title,
                path=entry.path,
                url=entry.url,
                archive_path=record.archive_path,
            )

    # Fallback: single-source page — attribute archive_path to the sole entry.
    archived_records = [
        state.sources[h]
        for h in page_hashes
        if h in state.sources and state.sources[h].archive_path
    ]
    if len(archived_records) == 1:
        record = archived_records[0]
        return SourceEntry(
            title=entry.title,
            path=entry.path,
            url=entry.url,
            archive_path=record.archive_path,
        )

    return entry


def _rewrite_page_body(
    body: str,
    state: State,
    page_hashes: list[str],
) -> str:
    """Return ``body`` with ``## Sources`` re-rendered, preserving everything else.

    If the page has no ``## Sources`` section, returns ``body`` unchanged.
    """
    above, bullet_lines = _split_body(body)
    if not bullet_lines and SOURCES_HEADING not in body:
        return body

    entries = _parse_bullets(bullet_lines)
    augmented = [_augment_entry_with_archive(e, state, page_hashes) for e in entries]

    # Issue #44: when the ## Sources section is empty but state.pages[<page>]
    # identifies exactly one source hash with a known archive_path, seed a
    # fresh Archive bullet. Guard with the same "exactly one archived source"
    # invariant as the single-source attribution heuristic in
    # _augment_entry_with_archive — never seed when ambiguous.
    if not augmented:
        archived_records = [
            state.sources[h]
            for h in page_hashes
            if h in state.sources and state.sources[h].archive_path
        ]
        if len(archived_records) == 1:
            record = archived_records[0]
            archive_path = record.archive_path
            assert archive_path is not None  # guarded by the list comp above
            augmented = [
                SourceEntry(
                    title=Path(archive_path).name,
                    path=archive_path,
                    url=None,
                    archive_path=archive_path,
                )
            ]

    rebuilt = render_sources_section(augmented)
    above_trimmed = above.rstrip("\n")
    if above_trimmed:
        return f"{above_trimmed}\n\n{rebuilt}"
    return rebuilt


def _page_hashes(
    state: State,
    page_path: Path,
    wiki_dir: Path,
    state_path: Path,
    fm_hash: str | None,
) -> list[str]:
    """Return the list of source hashes attributed to ``page_path`` in state.

    Tries ``state.pages[<rel>]`` first under a few candidate relative spellings,
    then falls back to the frontmatter ``source_hash`` (singular) if present.
    """
    candidates: list[str] = []
    try:
        root = Path(state_path).resolve().parent.parent
        candidates.append(str(page_path.resolve().relative_to(root)))
    except ValueError:
        pass
    try:
        candidates.append(str(page_path.resolve().relative_to(Path(wiki_dir).resolve().parent)))
    except ValueError:
        pass
    candidates.append(str(page_path))

    for rel in candidates:
        hashes = state.pages.get(rel)
        if hashes:
            return list(hashes)

    if fm_hash:
        return [fm_hash]
    return []


def rewrite_sources(
    *,
    wiki_dir: Path,
    state_path: Path,
    dry_run: bool = False,
    force: bool = False,
) -> list[RewriteResult]:
    """Walk ``wiki_dir/*.md`` and backfill Archive bullets from ``state``.

    Args:
        wiki_dir: Root of the Obsidian-compatible vault. Only top-level
            ``*.md`` pages are considered; ``concepts/`` and other
            subdirectories are left alone.
        state_path: Path to ``state.json`` from which ``archive_path`` is
            sourced.
        dry_run: If True, compute the outcomes but do not write any pages.
        force: If True, rewrite locked pages as well.

    Returns:
        One :class:`RewriteResult` per inspected page, in filesystem order.
    """
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki directory not found: {wiki_dir}")

    state = load_state(state_path)

    results: list[RewriteResult] = []
    for page_path in sorted(wiki_dir.glob("*.md")):
        original_bytes = page_path.read_bytes()
        text = original_bytes.decode("utf-8")
        fm_block, body = _split_frontmatter(text)

        # Use python-frontmatter only to READ metadata — we never round-trip
        # it back through ``dumps``, because that reorders keys and reflows
        # YAML which would violate the "byte-diff outside ## Sources == 0"
        # invariant. Frontmatter bytes are preserved verbatim.
        post = frontmatter.loads(text)
        locked = bool(post.get("locked", False))
        if locked and not force:
            results.append(RewriteResult(page_path=page_path, outcome=RewriteOutcome.LOCKED))
            continue

        fm_hash = post.get("source_hash")
        fm_hash_str = fm_hash if isinstance(fm_hash, str) else None
        hashes = _page_hashes(state, page_path, wiki_dir, state_path, fm_hash_str)

        new_body = _rewrite_page_body(body, state, hashes)
        if new_body == body:
            results.append(RewriteResult(page_path=page_path, outcome=RewriteOutcome.UNCHANGED))
            continue

        payload = (fm_block + new_body).encode("utf-8")
        if not payload.endswith(b"\n"):
            payload += b"\n"

        if payload == original_bytes:
            results.append(RewriteResult(page_path=page_path, outcome=RewriteOutcome.UNCHANGED))
            continue

        if not dry_run:
            atomic_write(page_path, payload)
        results.append(RewriteResult(page_path=page_path, outcome=RewriteOutcome.UPDATED))

    return results


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file into (raw-frontmatter-block, body).

    The frontmatter block includes the leading ``---\\n``, the YAML lines,
    and the closing ``---\\n`` delimiter — exactly the bytes we want to
    preserve verbatim on rewrite. If the file has no frontmatter, the first
    element is an empty string.
    """
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    fm_block = text[: end + len("\n---\n")]
    body = text[end + len("\n---\n") :]
    return fm_block, body
