"""Atomic wiki-page materialization with idempotent re-ingest.

Stories 02.1-001 (initial write) and 02.1-002 (idempotency via
``source_hash``). ``materialize`` is pure file I/O: it takes an LLM-drafted
markdown body (from a file or stdin) plus an archived source path, stamps
standard YAML frontmatter, and writes ``wiki/<slug>.md`` atomically.

Idempotency rules (02.1-002)
----------------------------
* If an existing page already carries the same ``source_hash``, skip the
  write entirely — mtime and body are untouched, status is ``SKIPPED``.
* If an existing page has ``locked: true`` in its frontmatter, skip the
  write and return status ``LOCKED``. The caller (CLI) surfaces a warning
  and exits 0 so batch flows keep moving.
* If the ``source_hash`` differs from what's on disk, rewrite the body and
  refresh ``ingested_at`` + ``source_hash`` (status ``UPDATED``). The prior
  hash is retained in ``state.pages[page]`` for auditability.
* ``force=True`` bypasses the lock check and always rewrites. The existing
  ``locked`` flag is preserved so a force-update doesn't silently unlock
  a protected page.

State lookup order: ``state.sources[hash]`` → existing frontmatter on
disk. State points to the canonical page; the on-disk frontmatter is the
authority for lock + current hash.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TextIO

import frontmatter

from ai_research.archive import slugify
from ai_research.state import SourceRecord, State, atomic_write, load_state, save_state
from ai_research.wiki.index_rebuild import rebuild_index
from ai_research.wiki.sources import SourceEntry, merge_sources_section
from ai_research.wiki.stubs import create_stubs_for_body, retire_stub_if_exists

__all__ = ["MaterializeResult", "MaterializeStatus", "materialize"]


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


class MaterializeStatus(StrEnum):
    """Outcome classifier for a ``materialize`` invocation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    LOCKED = "locked"


@dataclass(frozen=True)
class MaterializeResult:
    """Outcome of a ``materialize`` call."""

    page_path: Path
    source_hash: str
    slug: str
    status: MaterializeStatus = MaterializeStatus.CREATED


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


def _existing_page_for(
    state: State,
    source_hash: str,
    state_path: Path,
    candidate_path: Path,
) -> Path | None:
    """Return the page file on disk for ``source_hash`` if we can find it.

    Prefers ``state.sources[source_hash]`` (resolved relative to the state
    file's anchor); falls back to the slug-derived ``candidate_path``.
    """
    record = state.sources.get(source_hash)
    rel = record.page if record is not None else None
    if rel:
        anchor = Path(state_path).resolve().parent.parent
        absolute = Path(rel) if Path(rel).is_absolute() else anchor / rel
        if absolute.exists():
            return absolute
    if candidate_path.exists():
        return candidate_path
    return None


def materialize(  # noqa: PLR0913 — CLI-shaped keyword API, not hot path.
    *,
    source: Path,
    draft_path: Path | None,
    wiki_dir: Path,
    state_path: Path,
    now: datetime | None = None,
    stdin: TextIO | None = None,
    source_url: str | None = None,
    force: bool = False,
    index_path: Path | None = None,
    skip_index: bool = False,
) -> MaterializeResult:
    """Write ``wiki/<slug>.md`` from a draft and record state, idempotently.

    Args:
        source: Archived source file (hashed for ``source_hash``).
        draft_path: Markdown draft produced by the LLM. Exactly one of
            ``draft_path`` / ``stdin`` must be provided.
        wiki_dir: Root of the Obsidian-compatible wiki vault.
        state_path: Path to ``state.json`` (created if missing).
        now: Override wall clock for ``ingested_at`` (tests pass a fixed
            UTC timestamp).
        stdin: Text stream to read the draft from when ``draft_path`` is
            ``None`` — typically ``sys.stdin``.
        source_url: Original URL for web sources; recorded in the ## Sources section.
        force: Bypass ``locked: true`` and always rewrite, even when the
            ``source_hash`` is unchanged.
        index_path: If provided, rebuild this index file after a successful
            CREATED or UPDATED write (Story 02.2-002). SKIPPED/LOCKED never
            trigger a rebuild. No-op when ``skip_index`` is True or
            ``index_path`` is None.
        skip_index: Opt-out switch for bulk callers — suppress the auto
            index rebuild even when ``index_path`` is set.

    Returns:
        :class:`MaterializeResult` with the final page path, source hash,
        slug, and a :class:`MaterializeStatus` describing what happened.

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

    candidate_path = Path(wiki_dir) / f"{slug}.md"
    state: State = load_state(state_path)
    existing_page = _existing_page_for(state, source_hash, state_path, candidate_path)

    # If a page already exists for this slug (whether or not we know its
    # prior hash), inspect its frontmatter for the lock flag and current
    # hash before deciding whether to rewrite.
    on_disk_page = existing_page or (candidate_path if candidate_path.exists() else None)
    existing_post: frontmatter.Post | None = None
    if on_disk_page is not None:
        try:
            existing_post = frontmatter.loads(on_disk_page.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover — malformed frontmatter is rare
            existing_post = None

    page_path = existing_page or candidate_path

    if existing_post is not None:
        existing_hash = existing_post.get("source_hash")
        existing_locked = bool(existing_post.get("locked", False))

        # Lock check — force overrides, else bail.
        if existing_locked and not force:
            return MaterializeResult(
                page_path=page_path,
                source_hash=source_hash,
                slug=slug,
                status=MaterializeStatus.LOCKED,
            )

        # Hash unchanged and not forcing: pure no-op.
        if existing_hash == source_hash and not force:
            return MaterializeResult(
                page_path=page_path,
                source_hash=source_hash,
                slug=slug,
                status=MaterializeStatus.SKIPPED,
            )

        preserved_locked = existing_locked  # force-update retains lock flag
        status = MaterializeStatus.UPDATED
    else:
        preserved_locked = False
        status = MaterializeStatus.CREATED

    # Toolkit-owned metadata always wins over draft frontmatter.
    post["title"] = title
    post["source"] = str(source)
    post["ingested_at"] = timestamp.isoformat()
    post["source_hash"] = source_hash
    post["locked"] = preserved_locked

    page_path = Path(wiki_dir) / f"{slug}.md"

    # Merge ``## Sources`` back-reference (Story 02.2-003). Start with the draft
    # body and merge any prior sources from an existing page so re-materialization
    # with a new source appends rather than replacing.
    source_rel = _page_relative_source_path(source, wiki_dir)
    entry = SourceEntry(title=title, path=source_rel, url=source_url)
    # Graft prior sources into draft before merging the new one.
    base_body = post.content
    existing_body = _read_existing_body(page_path)
    if existing_body is not None:
        _, prior_bullets = _split_body_for_sources(existing_body)
        if prior_bullets:
            # Preserve existing sources: merge them into the draft body first.
            for line in prior_bullets:
                parsed = _parse_entry(line)
                if parsed is not None and parsed.path != source_rel:
                    base_body = merge_sources_section(base_body, parsed)
    post.content = merge_sources_section(base_body, entry)
    payload = frontmatter.dumps(post).encode("utf-8")
    if not payload.endswith(b"\n"):
        payload += b"\n"

    atomic_write(page_path, payload)

    # Retire any prior stub at wiki/concepts/<slug>.md now that the full page
    # is authoritative (Issue #32). Only stubs (``stub: true`` in frontmatter)
    # are removed; human-authored concept pages are preserved.
    retire_stub_if_exists(slug, wiki_dir=Path(wiki_dir))

    # Concept stubs: scan the drafted body for [[wikilinks]] and create
    # minimal stubs for any unresolved targets so the Obsidian graph stays
    # un-broken (Story 02.1-003). The host page's own slug is skipped to
    # avoid self-referential stubs.
    create_stubs_for_body(
        post.content,
        wiki_dir=Path(wiki_dir),
        now=timestamp,
        skip_slugs={slug},
    )

    # Update state.json after the page lands so a crash mid-page-write never
    # leaves state pointing at a non-existent file.
    # Reload — atomic_write doesn't touch state, but existing_page resolution
    # earlier may have been against a stale view if callers shared state.
    state = load_state(state_path)
    rel_page = _relative_or_absolute(page_path, state_path)
    # Preserve any existing archive_path (e.g. from a prior archive move);
    # 07.1-001 only records the shape, 07.1-002 will set archive_path here.
    prior = state.sources.get(source_hash)
    prior_archive = prior.archive_path if prior is not None else None
    state.sources[source_hash] = SourceRecord(page=rel_page, archive_path=prior_archive)
    existing_hashes = state.pages.get(rel_page, [])
    if source_hash not in existing_hashes:
        existing_hashes.append(source_hash)
    state.pages[rel_page] = existing_hashes
    save_state(state_path, state)

    # Auto-trigger index rebuild on CREATED/UPDATED (Story 02.2-002).
    # SKIPPED/LOCKED return earlier so we never reach here for those.
    if index_path is not None and not skip_index:
        rebuild_index(wiki_dir=Path(wiki_dir), index_path=Path(index_path))

    return MaterializeResult(
        page_path=page_path,
        source_hash=source_hash,
        slug=slug,
        status=status,
    )


def _split_body_for_sources(body: str) -> tuple[str, list[str]]:
    """Split body into (text-above-Sources, existing-bullet-lines).

    This is a helper for materialize to extract prior source entries
    for preservation during re-materialization. Delegates to sources module.
    """
    from ai_research.wiki.sources import _split_body

    return _split_body(body)


def _parse_entry(line: str) -> SourceEntry | None:
    """Parse a bullet line into a SourceEntry; return None if it doesn't match.

    Helper for materialize to parse existing sources for preservation.
    """
    from ai_research.wiki.sources import _parse_entry as sources_parse_entry

    return sources_parse_entry(line)


def _read_existing_body(page_path: Path) -> str | None:
    """Return the draft body of an existing page (without frontmatter) or None."""
    if not page_path.exists():
        return None
    try:
        post = frontmatter.loads(page_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - malformed page, treat as fresh
        return None
    return post.content


def _page_relative_source_path(source: Path, wiki_dir: Path) -> str:
    """Return the source path relative to the wiki vault's parent (repo root).

    Obsidian pages link with paths relative to the vault root. ``wiki_dir``'s
    parent is the natural anchor (the repo root in the default layout). If
    ``source`` lives outside that anchor, fall back to the absolute path.
    """
    try:
        anchor = Path(wiki_dir).resolve().parent
        return str(Path(source).resolve().relative_to(anchor))
    except ValueError:
        return str(Path(source).resolve())


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
