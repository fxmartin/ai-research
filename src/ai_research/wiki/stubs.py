"""Concept-stub creation for cross-linked wikilinks (Story 02.1-003).

When ``materialize`` writes a wiki page, any ``[[wikilink]]`` in the body that
doesn't yet resolve to a page in the vault gets a minimal stub written to
``wiki/concepts/<slug>.md``. Stubs keep the Obsidian graph un-broken and give
the LLM durable anchor points for future elaboration.

Stub frontmatter is intentionally minimal:

- ``type: concept`` — categorical marker so ``index-rebuild`` can list stubs
  separately if desired.
- ``stub: true`` — a one-bit flag the LLM can flip when it fills in the page.
- ``title`` — the original wikilink text (before slugification).
- ``created`` — ISO-8601 UTC timestamp.

Idempotency: if either ``wiki/<slug>.md`` (a full page) or
``wiki/concepts/<slug>.md`` (an existing stub) exists, creation is a no-op and
the existing path is returned — no mtime churn, no overwrite.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from ai_research.archive import slugify
from ai_research.state import atomic_write

__all__ = [
    "create_stub",
    "create_stubs_for_body",
    "extract_wikilinks",
    "retire_stub_if_exists",
]


# ``[[Target]]``, ``[[Target|alias]]``, ``[[Target#Anchor]]``,
# ``[[Target#Anchor|alias]]`` — we only care about the Target portion.
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")


def extract_wikilinks(body: str) -> list[str]:
    """Return the de-duplicated list of wikilink targets in ``body``.

    Targets are the portion before any ``#`` (anchor) or ``|`` (alias).
    Empty/whitespace-only targets are skipped. Order is preserved (first
    occurrence wins) so downstream stub creation is deterministic.
    """
    seen: dict[str, None] = {}
    for raw in _WIKILINK_RE.findall(body):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target and target not in seen:
            seen[target] = None
    return list(seen.keys())


def create_stub(
    concept: str,
    *,
    wiki_dir: Path,
    now: datetime | None = None,
) -> Path:
    """Create ``wiki/concepts/<slug>.md`` for ``concept`` if it doesn't exist.

    If a full page already lives at ``wiki/<slug>.md``, that path is returned
    unchanged — the concept is considered covered. Otherwise a minimal stub is
    written atomically (temp + rename), and the stub path is returned. If the
    stub already exists, it is left untouched and its path is returned.
    """
    slug = slugify(concept)
    wiki_dir = Path(wiki_dir)
    full_page = wiki_dir / f"{slug}.md"
    if full_page.exists():
        return full_page

    stub_path = wiki_dir / "concepts" / f"{slug}.md"
    if stub_path.exists():
        return stub_path

    timestamp = (now or datetime.now(tz=UTC)).astimezone(UTC)
    post = frontmatter.Post(
        content=f"Placeholder stub for [[{concept}]]. Expand when sources arrive.\n",
        **{
            "title": concept,
            "type": "concept",
            "stub": True,
            "created": timestamp.isoformat(),
        },
    )
    payload = frontmatter.dumps(post).encode("utf-8")
    if not payload.endswith(b"\n"):
        payload += b"\n"
    atomic_write(stub_path, payload)
    return stub_path


def retire_stub_if_exists(slug: str, *, wiki_dir: Path) -> Path | None:
    """Delete ``wiki/concepts/<slug>.md`` if it exists and is a stub.

    Called by ``materialize`` right after writing a full page at
    ``wiki/<slug>.md`` to reconcile the vault: any concept stub created by an
    earlier ingest for the same slug should be retired so the Obsidian graph
    has exactly one node per slug and ``index-rebuild`` doesn't list the stub
    alongside the now-authoritative page (Issue #32).

    A concept page is considered a retirable stub only when its frontmatter has
    ``stub: true``. A human-authored concept page at ``wiki/concepts/<slug>.md``
    (no ``stub: true`` marker) is preserved — we never clobber curated content.

    Returns the removed stub path on retirement, ``None`` otherwise.
    """
    stub_path = Path(wiki_dir) / "concepts" / f"{slug}.md"
    if not stub_path.exists():
        return None
    try:
        post = frontmatter.load(str(stub_path))
    except Exception:
        # Malformed stub — leave it alone and let a human triage.
        return None
    if post.metadata.get("stub") is not True:
        return None
    stub_path.unlink()
    return stub_path


def create_stubs_for_body(
    body: str,
    *,
    wiki_dir: Path,
    now: datetime | None = None,
    skip_slugs: set[str] | None = None,
) -> list[Path]:
    """Create stubs for every unresolved wikilink in ``body``.

    Args:
        body: Markdown body to scan for ``[[wikilinks]]``.
        wiki_dir: Root of the wiki vault; stubs land under ``concepts/``.
        now: Override timestamp for deterministic testing.
        skip_slugs: Slugs to ignore (e.g. the host page's own slug, to avoid a
            stub pointing back at the page being written).

    Returns:
        The list of newly-created stub paths (stable order, existing pages /
        stubs excluded).
    """
    skip = skip_slugs or set()
    wiki_dir = Path(wiki_dir)
    created: list[Path] = []
    for target in extract_wikilinks(body):
        slug = slugify(target)
        if slug in skip:
            continue
        full_page = wiki_dir / f"{slug}.md"
        stub_path = wiki_dir / "concepts" / f"{slug}.md"
        if full_page.exists() or stub_path.exists():
            # Idempotent: no-op, don't report as new.
            continue
        created.append(create_stub(target, wiki_dir=wiki_dir, now=now))
    return created
