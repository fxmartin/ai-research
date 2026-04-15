"""Page ``## Sources`` back-reference section.

Stories 02.2-003 (initial single-bullet form) and 08.1-001 (dual-bullet
URL + Archive form). Every materialized wiki page ends with a ``## Sources``
section linking each contributing source. The merge is idempotent:
re-materializing the same source is a no-op; re-materializing with a
*different* source appends without dropping prior entries.

Rendering shape (08.1-001)
--------------------------
For a source with both a URL and an archived local path::

    ## Sources
    - URL: https://example.com/foo
    - Archive: [foo.pdf](sources/2026/04/abcdef123456-foo.pdf)

PDF source (no URL) with an archive path::

    - Archive: [att.pdf](sources/2026/04/ab12abcd1234-att.pdf)

Pre-Epic-07 record (``archive_path=None``) carrying only a URL::

    - URL: https://example.com/foo

Fully legacy entries (no URL, no archive_path — only the deprecated
``path`` field) still render in the original ``- [title](path)`` form so
pages materialized before Epic-07 round-trip cleanly.

Design notes
------------
- We treat the body as plain text and locate ``## Sources`` heading by line.
  Anything before the heading is preserved verbatim. The list items below
  the heading are parsed in two passes: first the new dual-bullet
  ``- URL: ...`` / ``- Archive: [text](path)`` shape, then the legacy
  single-bullet ``- [title](path) (url)`` shape. This keeps pages written
  by earlier versions round-trippable.
- Each source is uniquely identified by a **dedupe key** — the archive
  path if present, else the URL, else the deprecated ``path``. Re-
  materializing a source with the same key replaces nothing and duplicates
  nothing; re-materializing with a *new* key appends.
- The merge is *additive only* — we never drop an existing entry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

__all__ = [
    "SourceEntry",
    "SOURCES_HEADING",
    "merge_sources_section",
    "render_sources_section",
]


SOURCES_HEADING = "## Sources"

# New dual-bullet shapes (08.1-001).
_URL_BULLET_RE = re.compile(r"^-\s*URL:\s*(?P<url>\S.*?)\s*$")
_ARCHIVE_BULLET_RE = re.compile(r"^-\s*Archive:\s*\[(?P<label>[^\]]+)\]\((?P<path>[^)]+)\)\s*$")

# Archive-label helper (08.3-001): strip the 12-char hex hash prefix from a
# basename so the visible Obsidian link label reads as a human-friendly filename
# (e.g. ``machines-of-loving-grace.md``) while the link target keeps the full
# hashed path. Defensive: if the basename doesn't carry the expected
# ``<12-hex>-`` prefix, return it unchanged.
_HASH_PREFIX_RE = re.compile(r"^[a-f0-9]{12}-")


def _archive_label(archive_path: str) -> str:
    """Derive a human-readable Obsidian link label from ``archive_path``.

    The final path segment is taken as the basename (including extension),
    then any leading ``<12-hex>-`` hash prefix is stripped. Non-conforming
    basenames (no hash prefix) are returned verbatim so the helper is safe
    for historical or hand-authored archive entries.
    """
    basename = PurePosixPath(archive_path).name
    return _HASH_PREFIX_RE.sub("", basename)


# Legacy single-bullet shape: "- [title](path)" with optional " (url)" suffix.
_LEGACY_ENTRY_RE = re.compile(
    r"^-\s*\[(?P<title>[^\]]+)\]\((?P<path>[^)]+)\)(?:\s*\((?P<url>https?://[^)]+)\))?\s*$"
)


@dataclass(frozen=True)
class SourceEntry:
    """One source contributing to a wiki page.

    Attributes:
        title: Human-readable label for the link text (legacy fallback).
        path: Repository-relative archive path used by the pre-08 single-
            bullet form. Kept for backwards compatibility with pages
            written before Epic-08 and for the fully-legacy fallback
            (no ``url``, no ``archive_path``).
        url: Optional original URL when the source was a web fetch.
        archive_path: Optional repository-relative path to the immutable
            archived copy (e.g. ``sources/2026/04/ab-x.pdf``). When set,
            drives the ``- Archive:`` bullet in the new dual-bullet form.
    """

    title: str
    path: str
    url: str | None = None
    archive_path: str | None = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("SourceEntry.title must be non-empty")
        if not self.path or not self.path.strip():
            raise ValueError("SourceEntry.path must be non-empty")

    @property
    def _dedupe_key(self) -> str:
        """Stable identity for merge dedupe.

        The archive path wins when present (post-Epic-07 sources); the URL
        is next (URL-only legacy records); finally the bare path (fully
        legacy PDF-only records).
        """
        if self.archive_path:
            return f"archive:{self.archive_path}"
        if self.url:
            return f"url:{self.url}"
        return f"path:{self.path}"

    def render(self) -> str:
        """Render this entry as one-or-two Markdown bullets (no trailing \\n).

        Shape selection:
          - ``archive_path`` set and ``url`` set → two bullets (URL + Archive).
          - ``archive_path`` set, no ``url`` → Archive bullet only.
          - ``url`` set, ``archive_path`` is None → URL bullet only.
          - Neither → legacy ``- [title](path)`` single bullet.
        """
        bullets: list[str] = []
        if self.url:
            bullets.append(f"- URL: {self.url}")
        if self.archive_path:
            label = _archive_label(self.archive_path)
            bullets.append(f"- Archive: [{label}]({self.archive_path})")
        if not bullets:
            # Fully legacy fallback — no URL, no archive_path. Keep the
            # historical single-bullet rendering so pre-Epic-08 pages with
            # only the deprecated ``path`` field continue to round-trip.
            bullets.append(f"- [{self.title}]({self.path})")
        return "\n".join(bullets)


def render_sources_section(entries: list[SourceEntry]) -> str:
    """Render a fresh ``## Sources`` section from ``entries``.

    Returns the heading plus one or two bullets per entry (see
    :meth:`SourceEntry.render`), terminated by ``\\n``.
    """
    lines = [SOURCES_HEADING]
    lines.extend(entry.render() for entry in entries)
    return "\n".join(lines) + "\n"


def _split_body(body: str) -> tuple[str, list[str], str]:
    """Split ``body`` into (text-above-Sources, bullet-lines, trailing).

    ``trailing`` is everything from the first non-bullet, non-blank line
    (or the next H1/H2) after the ``## Sources`` bullets through EOF.
    This guards against silent data loss when the drafter places
    ``## Sources`` before other H2 sections (Issue #48).

    If no ``## Sources`` heading exists, returns ``(body, [], "")``.
    """
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == SOURCES_HEADING:
            above = "\n".join(lines[:idx])
            below = lines[idx + 1 :]
            bullets: list[str] = []
            end = 0
            for j, raw in enumerate(below):
                stripped = raw.strip()
                if stripped.startswith("## ") or stripped.startswith("# "):
                    end = j
                    break
                if stripped == "":
                    # Blank line after at least one bullet terminates the
                    # bullets block; a leading blank right after ``## Sources``
                    # (empty section) also terminates, leaving bullets empty.
                    end = j
                    break
                if stripped.startswith("-"):
                    bullets.append(raw)
                    end = j + 1
                else:
                    # Non-bullet, non-blank content — hand off to trailing.
                    end = j
                    break
            else:
                # Loop completed without break: all of ``below`` was consumed
                # as bullets (or ``below`` was empty).
                end = len(below)
            trailing = "\n".join(below[end:]).lstrip("\n")
            return above, bullets, trailing
    return body, [], ""


def _parse_bullets(bullet_lines: list[str]) -> list[SourceEntry]:
    """Parse a sequence of bullet lines into SourceEntry objects.

    Walks the lines sequentially, pairing adjacent ``- URL:`` and
    ``- Archive:`` bullets into a single :class:`SourceEntry`. A standalone
    URL or Archive bullet becomes a one-sided entry. Unrecognized lines
    fall through to the legacy single-bullet parser and, failing that,
    are silently dropped (existing 02.2-003 behavior).
    """
    entries: list[SourceEntry] = []
    i = 0
    n = len(bullet_lines)
    while i < n:
        line = bullet_lines[i].strip()

        url_match = _URL_BULLET_RE.match(line)
        if url_match:
            url = url_match.group("url")
            archive_path: str | None = None
            label: str | None = None
            # Pair with immediately-following Archive bullet, if any.
            if i + 1 < n:
                next_line = bullet_lines[i + 1].strip()
                arch_match = _ARCHIVE_BULLET_RE.match(next_line)
                if arch_match:
                    archive_path = arch_match.group("path")
                    label = arch_match.group("label")
                    i += 1
            title = label or url
            path = archive_path or url
            entries.append(
                SourceEntry(
                    title=title,
                    path=path,
                    url=url,
                    archive_path=archive_path,
                )
            )
            i += 1
            continue

        arch_match = _ARCHIVE_BULLET_RE.match(line)
        if arch_match:
            # Named groups are non-optional here because the regex requires
            # both to match; coerce to str to satisfy the type checker.
            archive_path = str(arch_match.group("path"))
            label = str(arch_match.group("label"))
            entries.append(
                SourceEntry(
                    title=label,
                    path=archive_path,
                    url=None,
                    archive_path=archive_path,
                )
            )
            i += 1
            continue

        legacy_match = _LEGACY_ENTRY_RE.match(line)
        if legacy_match:
            entries.append(
                SourceEntry(
                    title=legacy_match.group("title"),
                    path=legacy_match.group("path"),
                    url=legacy_match.group("url"),
                    archive_path=None,
                )
            )
            i += 1
            continue

        # Unparsable — skip, matching prior 02.2-003 tolerance.
        i += 1
    return entries


def _parse_entry(line: str) -> SourceEntry | None:
    """Parse a single bullet line into a SourceEntry.

    Used by callers that still want a one-line parse (e.g. materialize's
    prior-source grafting). Returns ``None`` if the line doesn't match any
    known shape. For the dual-bullet form, this returns a one-sided entry
    (only URL, or only Archive) because there is no adjacent line
    context — full pairing happens in :func:`_parse_bullets`.
    """
    entries = _parse_bullets([line])
    return entries[0] if entries else None


def merge_sources_section(body: str, new_entry: SourceEntry) -> str:
    """Return ``body`` with ``new_entry`` merged into a ``## Sources`` section.

    Behavior:
    - No existing section: append ``\\n## Sources\\n<bullets>\\n`` at the end.
    - Existing section, same dedupe key already present: no-op (idempotent).
    - Existing section, new key: append a new entry, preserving prior
      entries in their original order.

    Dedupe is keyed on :attr:`SourceEntry._dedupe_key` — archive path wins,
    URL is the fallback, raw path is the last resort. This lets
    re-materializing the same source (even after its single-bullet legacy
    record has been rewritten to the dual-bullet form) remain idempotent.
    """
    above, bullet_lines, trailing = _split_body(body)

    existing = _parse_bullets(bullet_lines)

    keys_seen = {e._dedupe_key for e in existing}
    if new_entry._dedupe_key not in keys_seen:
        existing.append(new_entry)

    rebuilt_section = render_sources_section(existing)

    if not bullet_lines and SOURCES_HEADING not in body:
        prefix = above.rstrip("\n")
        if prefix:
            return f"{prefix}\n\n{rebuilt_section}"
        return rebuilt_section

    above_trimmed = above.rstrip("\n")
    if above_trimmed:
        result = f"{above_trimmed}\n\n{rebuilt_section}"
    else:
        result = rebuilt_section

    # Re-attach any body content that followed the Sources section
    # (Issue #48): Summary / Key Claims / Connections etc. must survive.
    if trailing:
        result = f"{result.rstrip()}\n\n{trailing}"
        if not result.endswith("\n"):
            result += "\n"
    return result
