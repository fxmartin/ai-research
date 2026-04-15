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
    """Pre-Epic-07 record (``archive_path=None``) with a URL emits URL-only."""
    entries = [
        SourceEntry(
            title="Karpathy LLM Wiki",
            path="sources/2026/04/cd34-karpathy.md",
            url="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f",
        )
    ]
    out = render_sources_section(entries)
    assert "## Sources\n" in out
    assert "- URL: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f" in out
    # No orphan Archive bullet when archive_path is None.
    assert "Archive:" not in out


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
    """URL-only entry (archive_path=None) appends as a single URL bullet."""
    body = "# Title\n\nBody.\n"
    entry = SourceEntry(
        title="Karpathy Gist",
        path="sources/2026/04/xx-gist.md",
        url="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f",
    )
    out = merge_sources_section(body, entry)
    assert "## Sources" in out
    assert "- URL: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f" in out
    assert "Archive:" not in out


# ---------------------------------------------------------------------------
# Story 08.1-001 — Dual-bullet rendering (URL + Archive)
# ---------------------------------------------------------------------------


def test_render_dual_bullet_url_and_archive() -> None:
    """URL + archive_path → two bullets, URL first, Archive second."""
    entry = SourceEntry(
        title="Foo",
        path="sources/2026/04/abcdef-foo.pdf",
        url="https://example.com/foo",
        archive_path="sources/2026/04/abcdef-foo.pdf",
    )
    out = render_sources_section([entry])
    assert out == (
        "## Sources\n"
        "- URL: https://example.com/foo\n"
        "- Archive: [abcdef-foo.pdf](sources/2026/04/abcdef-foo.pdf)\n"
    )


def test_render_archive_only_no_url() -> None:
    """PDF source with no URL → only the Archive bullet is emitted."""
    entry = SourceEntry(
        title="Opus Card",
        path="sources/2026/02/deadbeef-opus.pdf",
        url=None,
        archive_path="sources/2026/02/deadbeef-opus.pdf",
    )
    out = render_sources_section([entry])
    assert out == (
        "## Sources\n- Archive: [deadbeef-opus.pdf](sources/2026/02/deadbeef-opus.pdf)\n"
    )
    assert "URL:" not in out


def test_render_url_only_legacy_archive_path_none() -> None:
    """archive_path=None + url set → only the URL bullet (no orphan Archive)."""
    entry = SourceEntry(
        title="Legacy Web",
        path="sources/2026/04/xx-legacy.md",
        url="https://example.com/legacy",
        archive_path=None,
    )
    out = render_sources_section([entry])
    assert "- URL: https://example.com/legacy" in out
    assert "Archive:" not in out


def test_parse_round_trip_dual_bullet() -> None:
    """Dual-bullet rendering parses back into an entry with both fields."""
    entry = SourceEntry(
        title="Foo",
        path="sources/2026/04/abcdef-foo.pdf",
        url="https://example.com/foo",
        archive_path="sources/2026/04/abcdef-foo.pdf",
    )
    body = "# T\n\nBody.\n"
    rendered = merge_sources_section(body, entry)
    # Re-merging the identical entry is a no-op (idempotent round-trip via parser).
    twice = merge_sources_section(rendered, entry)
    assert rendered == twice
    # Both bullets present exactly once.
    assert rendered.count("- URL: https://example.com/foo") == 1
    assert rendered.count("- Archive: [abcdef-foo.pdf](sources/2026/04/abcdef-foo.pdf)") == 1


def test_merge_two_dual_bullet_sources_preserves_both_pairs() -> None:
    """Re-materializing with an additional source yields two URL+Archive pairs."""
    body = "# T\n\nBody.\n"
    first = SourceEntry(
        title="First",
        path="sources/2026/04/aaa-first.pdf",
        url="https://example.com/first",
        archive_path="sources/2026/04/aaa-first.pdf",
    )
    second = SourceEntry(
        title="Second",
        path="sources/2026/04/bbb-second.pdf",
        url="https://example.com/second",
        archive_path="sources/2026/04/bbb-second.pdf",
    )
    step1 = merge_sources_section(body, first)
    step2 = merge_sources_section(step1, second)

    # Exactly one heading.
    assert step2.count("## Sources") == 1
    # Both URL bullets.
    assert "- URL: https://example.com/first" in step2
    assert "- URL: https://example.com/second" in step2
    # Both Archive bullets.
    assert "- Archive: [aaa-first.pdf](sources/2026/04/aaa-first.pdf)" in step2
    assert "- Archive: [bbb-second.pdf](sources/2026/04/bbb-second.pdf)" in step2
    # Ordering: first URL/Archive pair precedes the second URL/Archive pair.
    first_url_idx = step2.index("- URL: https://example.com/first")
    first_arch_idx = step2.index("aaa-first.pdf](sources/2026/04/aaa-first.pdf)")
    second_url_idx = step2.index("- URL: https://example.com/second")
    assert first_url_idx < first_arch_idx < second_url_idx


def test_merge_dual_bullet_idempotent_by_archive_path() -> None:
    """Re-merging a source with the same archive_path is a no-op."""
    entry = SourceEntry(
        title="Foo",
        path="sources/2026/04/abcdef-foo.pdf",
        url="https://example.com/foo",
        archive_path="sources/2026/04/abcdef-foo.pdf",
    )
    body = "# T\n\nBody.\n"
    once = merge_sources_section(body, entry)
    twice = merge_sources_section(once, entry)
    assert once == twice


def test_legacy_single_bullet_still_parses_on_merge() -> None:
    """Existing pages with pre-Epic-08 single-bullet sources round-trip safely."""
    # Legacy-shaped body: single bullet with title + path + parenthesised URL.
    body = (
        "# T\n\nBody.\n\n"
        "## Sources\n"
        "- [Old Title](sources/2026/04/legacy.pdf) (https://example.com/old)\n"
    )
    new_entry = SourceEntry(
        title="New",
        path="sources/2026/04/new.pdf",
        url="https://example.com/new",
        archive_path="sources/2026/04/new.pdf",
    )
    out = merge_sources_section(body, new_entry)
    # Legacy entry preserved (re-rendered in whatever shape the parser picks —
    # key thing is it isn't dropped and isn't duplicated).
    assert "https://example.com/old" in out
    assert "- URL: https://example.com/new" in out
    assert "- Archive: [new.pdf](sources/2026/04/new.pdf)" in out


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


# ---------------------------------------------------------------------------
# Story 08.3-001 — Archive bullet uses human-readable filename as link label
# ---------------------------------------------------------------------------


def test_archive_label_strips_hash12_prefix() -> None:
    """Hash-prefixed archive basename → label without the `<12-hex>-` prefix.

    AC: ``sources/2026/04/abcdef123456-machines-of-loving-grace.md`` →
    label ``machines-of-loving-grace.md``. The link target retains the full
    hashed path.
    """
    archive = "sources/2026/04/abcdef123456-machines-of-loving-grace.md"
    entry = SourceEntry(
        title="Machines of Loving Grace",
        path=archive,
        archive_path=archive,
    )
    out = render_sources_section([entry])
    assert f"- Archive: [machines-of-loving-grace.md]({archive})\n" in out


def test_archive_label_pdf_keeps_extension() -> None:
    """PDF basename keeps its `.pdf` extension in the visible label."""
    archive = "sources/2026/02/deadbeef1234-opus-card.pdf"
    entry = SourceEntry(
        title="Opus Card",
        path=archive,
        archive_path=archive,
    )
    out = render_sources_section([entry])
    assert f"- Archive: [opus-card.pdf]({archive})\n" in out


def test_archive_label_without_hash_prefix_is_verbatim() -> None:
    """Defensive: a basename without a 12-hex-prefix is used as-is.

    Covers hand-authored or pre-hash-scheme paths. We must not accidentally
    strip partial or shorter prefixes.
    """
    archive = "sources/2026/04/plain-name.pdf"
    entry = SourceEntry(
        title="Plain",
        path=archive,
        archive_path=archive,
    )
    out = render_sources_section([entry])
    assert f"- Archive: [plain-name.pdf]({archive})\n" in out


def test_archive_label_short_hexlike_prefix_not_stripped() -> None:
    """Prefixes shorter than 12 hex chars are preserved (no false-positive strip)."""
    archive = "sources/2026/04/abc-short.pdf"
    entry = SourceEntry(
        title="Short",
        path=archive,
        archive_path=archive,
    )
    out = render_sources_section([entry])
    # The 3-char hex-like prefix must remain in the label.
    assert f"- Archive: [abc-short.pdf]({archive})\n" in out


# ---------------------------------------------------------------------------
# Issue #48 — preserve body content after ## Sources section
# ---------------------------------------------------------------------------


def test_merge_preserves_trailing_h2_sections_after_sources() -> None:
    """Regression: draft with ## Sources before ## Summary must keep Summary.

    Pre-fix, _split_body dropped everything after the Sources bullets, so
    materialize silently emptied Summary / Key Claims / Connections.
    """
    body = (
        "# Title\n"
        "## Sources\n"
        "- URL: https://example.com\n"
        "\n"
        "## Summary\n"
        "Body content here.\n"
        "\n"
        "## Key Claims\n"
        "- A claim.\n"
    )
    entry = SourceEntry(
        title="Example",
        path="sources/2026/04/aa-example.md",
        url="https://example.com",
    )
    out = merge_sources_section(body, entry)
    assert "## Summary" in out
    assert "Body content here." in out
    assert "## Key Claims" in out
    assert "- A claim." in out
    # Sources section still intact with the URL bullet.
    assert "## Sources" in out
    assert "- URL: https://example.com" in out


def test_merge_preserves_trailing_is_idempotent() -> None:
    """Calling merge_sources_section twice with the same entry is a no-op."""
    body = "# Title\n## Sources\n- URL: https://example.com\n\n## Summary\nBody.\n"
    entry = SourceEntry(
        title="Example",
        path="sources/2026/04/aa-example.md",
        url="https://example.com",
    )
    once = merge_sources_section(body, entry)
    twice = merge_sources_section(once, entry)
    assert once == twice


def test_merge_no_sources_heading_preserves_full_body() -> None:
    """No existing ## Sources → full original body preserved, section appended."""
    body = "# Title\n\n## Summary\nAll the content.\n\n## Key Claims\n- X.\n"
    entry = SourceEntry(
        title="Example",
        path="sources/2026/04/aa-example.md",
        url="https://example.com",
    )
    out = merge_sources_section(body, entry)
    # Original body fully preserved at the top.
    assert out.startswith("# Title\n\n## Summary\nAll the content.\n\n## Key Claims\n- X.\n")
    # Sources appended at the end.
    assert out.rstrip().endswith("- URL: https://example.com")


def test_merge_empty_sources_section_next_h2_immediately_preserves_trailing() -> None:
    """Empty ## Sources (no bullets) followed directly by another H2 keeps trailing."""
    body = "# Title\n## Sources\n## Summary\nBody text.\n"
    entry = SourceEntry(
        title="Example",
        path="sources/2026/04/aa-example.md",
        url="https://example.com",
    )
    out = merge_sources_section(body, entry)
    assert "## Summary" in out
    assert "Body text." in out
    assert "- URL: https://example.com" in out
