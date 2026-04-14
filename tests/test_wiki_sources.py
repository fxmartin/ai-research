"""Tests for ai_research.wiki.sources (Story 02.2-003).

The Sources module owns the ``## Sources`` back-reference section appended to
every materialized wiki page. The section is idempotent: running materialize
twice with the same source yields a single entry; re-materializing with a
different source appends rather than replaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_research.wiki.sources import (
    SourceEntry,
    merge_sources_section,
    render_sources_section,
)


def test_render_sources_section_single_file_entry() -> None:
    entries = [SourceEntry(title="Attention Is All You Need", path="sources/2026/04/ab12-att.pdf")]
    out = render_sources_section(entries)
    assert out == ("## Sources\n- [Attention Is All You Need](sources/2026/04/ab12-att.pdf)\n")


def test_render_sources_section_url_entry_includes_original_url() -> None:
    entries = [
        SourceEntry(
            title="Karpathy LLM Wiki",
            path="sources/2026/04/cd34-karpathy.md",
            url="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f",
        )
    ]
    out = render_sources_section(entries)
    assert "## Sources\n" in out
    assert "[Karpathy LLM Wiki](sources/2026/04/cd34-karpathy.md)" in out
    assert "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f" in out


def test_merge_sources_section_appends_to_body_without_existing_section() -> None:
    body = "# Title\n\nBody paragraph.\n"
    entry = SourceEntry(title="Paper", path="sources/x.pdf")
    out = merge_sources_section(body, entry)
    assert out.startswith("# Title\n\nBody paragraph.")
    assert out.rstrip().endswith("- [Paper](sources/x.pdf)")
    assert "## Sources" in out


def test_merge_sources_section_idempotent_same_source(tmp_path: Path) -> None:
    body = "# Title\n\nBody.\n"
    entry = SourceEntry(title="Paper", path="sources/x.pdf")
    once = merge_sources_section(body, entry)
    twice = merge_sources_section(once, entry)
    assert once == twice
    # Only one list entry.
    assert twice.count("- [Paper](sources/x.pdf)") == 1


def test_merge_sources_section_appends_new_source_when_path_differs() -> None:
    body = "# Title\n\nBody.\n"
    first = merge_sources_section(body, SourceEntry(title="First", path="sources/a.pdf"))
    second = merge_sources_section(first, SourceEntry(title="Second", path="sources/b.pdf"))
    assert "- [First](sources/a.pdf)" in second
    assert "- [Second](sources/b.pdf)" in second
    # Only one ## Sources header.
    assert second.count("## Sources") == 1


def test_merge_sources_section_preserves_user_body_after_existing_section() -> None:
    body = "# Title\n\nBody paragraph.\n\n## Sources\n- [First](sources/a.pdf)\n"
    entry = SourceEntry(title="Second", path="sources/b.pdf")
    out = merge_sources_section(body, entry)
    # Original entry preserved.
    assert "- [First](sources/a.pdf)" in out
    assert "- [Second](sources/b.pdf)" in out
    # Body above the section is preserved verbatim.
    assert out.startswith("# Title\n\nBody paragraph.\n\n## Sources\n")


def test_merge_sources_section_url_entry_includes_url_on_append() -> None:
    body = "# Title\n\nBody.\n"
    entry = SourceEntry(
        title="Karpathy Gist",
        path="sources/2026/04/xx-gist.md",
        url="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f",
    )
    out = merge_sources_section(body, entry)
    assert "## Sources" in out
    assert "[Karpathy Gist](sources/2026/04/xx-gist.md)" in out
    assert "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f" in out


def test_merge_sources_section_matches_by_path_not_title() -> None:
    """If the same path re-appears with a different title, we do not duplicate."""
    body = "# T\n\nBody.\n"
    a = merge_sources_section(body, SourceEntry(title="Old", path="sources/a.pdf"))
    b = merge_sources_section(a, SourceEntry(title="New", path="sources/a.pdf"))
    # Exactly one entry for sources/a.pdf.
    assert b.count("sources/a.pdf") == 1


def test_merge_sources_section_trailing_newline() -> None:
    body = "# T\n\nBody."  # no trailing newline
    out = merge_sources_section(body, SourceEntry(title="P", path="sources/x.pdf"))
    assert out.endswith("\n")


def test_source_entry_rejects_blank_path() -> None:
    with pytest.raises(ValueError):
        SourceEntry(title="x", path="")


def test_merge_stops_collecting_bullets_at_blank_line() -> None:
    """A blank line inside the Sources section terminates bullet collection."""
    body = "# T\n\n## Sources\n- [First](sources/a.pdf)\n\n- [NotParsed](sources/b.pdf)\n"
    out = merge_sources_section(body, SourceEntry(title="New", path="sources/c.pdf"))
    assert "- [First](sources/a.pdf)" in out
    assert "- [New](sources/c.pdf)" in out


def test_merge_stops_collecting_bullets_at_next_heading() -> None:
    """A following heading terminates bullet collection."""
    body = "## Sources\n- [First](sources/a.pdf)\n## Footer\n"
    out = merge_sources_section(body, SourceEntry(title="New", path="sources/c.pdf"))
    assert "- [First](sources/a.pdf)" in out
    assert "- [New](sources/c.pdf)" in out


def test_merge_ignores_unparsable_bullet_lines() -> None:
    """Unrecognized lines under ## Sources are dropped from the dedupe set."""
    body = "## Sources\n- just a note not a link\n"
    out = merge_sources_section(body, SourceEntry(title="A", path="sources/a.pdf"))
    assert "- [A](sources/a.pdf)" in out


def test_merge_empty_body_appends_section() -> None:
    """A completely empty body still produces a valid Sources section."""
    out = merge_sources_section("", SourceEntry(title="X", path="sources/x.pdf"))
    assert out.startswith("## Sources\n")
    assert "- [X](sources/x.pdf)" in out


def test_merge_body_that_is_only_sources_heading() -> None:
    """Body with only '## Sources' heading (no prefix, no bullets) still merges."""
    out = merge_sources_section("## Sources\n", SourceEntry(title="X", path="sources/x.pdf"))
    assert out.startswith("## Sources\n")
    assert "- [X](sources/x.pdf)" in out


def test_source_entry_rejects_blank_title() -> None:
    with pytest.raises(ValueError):
        SourceEntry(title="", path="sources/x.pdf")
