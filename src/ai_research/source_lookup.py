"""Reverse-lookup a wiki page slug to the archived source bytes (Story 07.3-001).

Given a slug (e.g. ``dario-amodei``), resolve it to:

1. the full wiki page path recorded in :attr:`State.pages` (e.g.
   ``wiki/dario-amodei.md``);
2. the first source hash contributing to that page;
3. the ``archive_path`` stored in :attr:`State.sources`.

This module is deliberately read-only and free of side effects so it can be
called safely from CLI verbs, ``/ask`` follow-ups, or programmatic tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_research.state import State

__all__ = [
    "LookupError",
    "SourceLookupResult",
    "StubOnlyError",
    "UnknownSlugError",
    "lookup_source_by_slug",
]


@dataclass(frozen=True)
class SourceLookupResult:
    """Outcome of a successful reverse-lookup.

    ``archive_path`` is ``None`` for pre-07.1 ingest records that predate the
    archive-after-ingest epic; callers should surface that explicitly rather
    than treating it as an error.
    """

    slug: str
    page: str
    source_hash: str
    archive_path: str | None


class LookupError(Exception):
    """Base class for reverse-lookup failures."""


class StubOnlyError(LookupError):
    """Slug resolves only to a concept stub under ``wiki/concepts/``."""


class UnknownSlugError(LookupError):
    """Slug is not a materialized page and not a stub either."""


def _page_slug(page_path: str) -> str:
    """Return the slug portion of a recorded page path."""
    return Path(page_path).stem


def lookup_source_by_slug(
    slug: str,
    state: State,
    *,
    wiki_dir: Path,
) -> SourceLookupResult:
    """Resolve ``slug`` against ``state.pages`` and return archive info.

    Resolution order:

    1. Exact stem match against any key in :attr:`State.pages` — this is the
       authoritative source of "fully materialized page" for a slug.
    2. If no page match, check ``wiki_dir/concepts/<slug>.md`` — if present,
       raise :class:`StubOnlyError` with a message explaining the slug is a
       concept stub without archived bytes.
    3. Otherwise raise :class:`UnknownSlugError`.

    Pre-07.1 records where ``archive_path is None`` resolve successfully; the
    caller is expected to format the "source not archived" message.
    """
    for page_path, hashes in state.pages.items():
        if _page_slug(page_path) == slug and hashes:
            source_hash = hashes[0]
            record = state.sources.get(source_hash)
            archive_path = record.archive_path if record is not None else None
            return SourceLookupResult(
                slug=slug,
                page=page_path,
                source_hash=source_hash,
                archive_path=archive_path,
            )

    stub_path = Path(wiki_dir) / "concepts" / f"{slug}.md"
    if stub_path.exists():
        raise StubOnlyError(
            f"'{slug}' is a concept stub at {stub_path}; no archived source bytes exist for stubs."
        )

    raise UnknownSlugError(
        f"no wiki page found for slug '{slug}' (searched state.pages and {wiki_dir}/concepts/)."
    )
