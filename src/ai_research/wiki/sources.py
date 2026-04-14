"""Page ``## Sources`` back-reference section (Story 02.2-003).

Every materialized wiki page ends with a ``## Sources`` section linking each
contributing archived source. The merge is idempotent: re-materializing the
same source is a no-op; re-materializing with a *different* source appends
without dropping prior entries.

Design notes
------------
- We treat the body as plain text and locate ``## Sources`` heading by line.
  Anything before the heading is preserved verbatim. The list items below the
  heading are parsed minimally (``- [title](path)`` pattern) so we can dedupe
  by **archive path**, the only stable identifier.
- URL sources carry both the archived snapshot path AND the original URL, per
  AC3. The URL is rendered as a parenthetical suffix on the same list line so
  the section remains a flat bullet list (Obsidian renders cleanly).
- The merge is *additive only* — we never drop or rewrite an existing entry.
  The matching wiki page is the source of truth; this module's job is to
  guarantee one bullet per archive path, in insertion order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "SourceEntry",
    "SOURCES_HEADING",
    "merge_sources_section",
    "render_sources_section",
]


SOURCES_HEADING = "## Sources"

# Captures "- [title](path)" with an optional " (url)" suffix. We anchor on the
# leading dash so other Markdown content under ## Sources is left untouched.
_ENTRY_RE = re.compile(
    r"^-\s*\[(?P<title>[^\]]+)\]\((?P<path>[^)]+)\)(?:\s*\((?P<url>https?://[^)]+)\))?\s*$"
)


@dataclass(frozen=True)
class SourceEntry:
    """One archived source contributing to a wiki page.

    Attributes:
        title: Human-readable label for the link text.
        path: Repository-relative archive path (e.g. ``sources/2026/04/ab-x.pdf``).
        url: Optional original URL when the source was a web fetch.
    """

    title: str
    path: str
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("SourceEntry.title must be non-empty")
        if not self.path or not self.path.strip():
            raise ValueError("SourceEntry.path must be non-empty")

    def render(self) -> str:
        """Render this entry as a single Markdown bullet line (no trailing \\n)."""
        line = f"- [{self.title}]({self.path})"
        if self.url:
            line += f" ({self.url})"
        return line


def render_sources_section(entries: list[SourceEntry]) -> str:
    """Render a fresh ``## Sources`` section from ``entries``.

    Returns the heading plus one bullet per entry, terminated by ``\\n``.
    Used by callers that want the section text without an existing body to
    merge into (e.g. tests and golden-file fixtures).
    """
    lines = [SOURCES_HEADING]
    lines.extend(entry.render() for entry in entries)
    return "\n".join(lines) + "\n"


def _split_body(body: str) -> tuple[str, list[str]]:
    """Split ``body`` into (text-above-Sources, existing-bullet-lines).

    If no ``## Sources`` heading exists, the second tuple element is an empty
    list and the first is the entire body.
    """
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == SOURCES_HEADING:
            above = "\n".join(lines[:idx])
            below = lines[idx + 1 :]
            # Bullet lines under the section, until a blank-line gap or new heading.
            bullets: list[str] = []
            for raw in below:
                stripped = raw.strip()
                if stripped.startswith("## ") or stripped.startswith("# "):
                    break
                if stripped == "":
                    # Allow blank lines inside the section but stop collecting
                    # bullets once we hit one (keep parser conservative).
                    break
                bullets.append(raw)
            return above, bullets
    return body, []


def _parse_entry(line: str) -> SourceEntry | None:
    """Parse a bullet line into a SourceEntry; return None if it doesn't match."""
    m = _ENTRY_RE.match(line.strip())
    if not m:
        return None
    return SourceEntry(
        title=m.group("title"),
        path=m.group("path"),
        url=m.group("url"),
    )


def merge_sources_section(body: str, new_entry: SourceEntry) -> str:
    """Return ``body`` with ``new_entry`` merged into a ``## Sources`` section.

    Behavior:
    - No existing section: append ``\\n## Sources\\n- [...](...)\\n`` at the end.
    - Existing section, ``new_entry.path`` already present: no-op (idempotent).
    - Existing section, new path: append a new bullet, preserving prior entries
      in their original order.
    """
    above, bullet_lines = _split_body(body)

    existing: list[SourceEntry] = []
    for line in bullet_lines:
        parsed = _parse_entry(line)
        if parsed is not None:
            existing.append(parsed)

    paths_seen = {e.path for e in existing}
    if new_entry.path not in paths_seen:
        existing.append(new_entry)

    rebuilt_section = render_sources_section(existing)

    if not bullet_lines and SOURCES_HEADING not in body:
        # Fresh append: ensure a blank-line gap between body and section.
        prefix = above.rstrip("\n")
        if prefix:
            return f"{prefix}\n\n{rebuilt_section}"
        return rebuilt_section

    above_trimmed = above.rstrip("\n")
    if above_trimmed:
        return f"{above_trimmed}\n\n{rebuilt_section}"
    return rebuilt_section
