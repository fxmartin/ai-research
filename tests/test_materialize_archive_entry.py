"""Story 08.1-002: materialize plumbs archive_path into the SourceEntry.

Verifies that the ``## Sources`` section of a freshly-materialized page
contains the correct combination of ``URL:`` and ``Archive:`` bullets
based on the source shape and ``--no-archive`` flag.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from ai_research.wiki.materialize import MaterializeStatus, materialize

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def _vault(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Set up a repo-shaped workspace. Returns (raw, wiki, state)."""
    wiki = tmp_path / "wiki"
    raw = wiki / "raw"
    raw.mkdir(parents=True)
    state = tmp_path / ".ai-research" / "state.json"
    return raw, wiki, state


def _draft(tmp_path: Path, body: str = "# Foo\n\nBody.\n") -> Path:
    d = tmp_path / "draft.md"
    d.write_text(body, encoding="utf-8")
    return d


def _body_of(page_path: Path) -> str:
    return frontmatter.loads(page_path.read_text(encoding="utf-8")).content


def test_created_with_url_emits_url_and_archive_bullets(tmp_path: Path) -> None:
    """URL + default archive → both bullets appear in ## Sources."""
    raw, wiki, state_path = _vault(tmp_path)
    src = raw / "foo.md"
    src.write_text("raw bytes\n", encoding="utf-8")
    draft = _draft(tmp_path)

    result = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        source_url="https://example.com/foo",
    )
    assert result.status is MaterializeStatus.CREATED

    body = _body_of(result.page_path)
    assert "## Sources" in body
    assert "- URL: https://example.com/foo" in body
    # Archive bullet includes the repo-root-relative POSIX path twice
    # (markdown-link label and target).
    hash12 = result.source_hash[:12]
    expected = f"- Archive: [sources/2026/04/{hash12}-foo.md](sources/2026/04/{hash12}-foo.md)"
    assert expected in body


def test_created_without_url_emits_archive_only(tmp_path: Path) -> None:
    """PDF-like source with no URL → only the Archive bullet is emitted."""
    raw, wiki, state_path = _vault(tmp_path)
    src = raw / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\n%binary\n")
    draft = _draft(tmp_path, "# Paper\n\nBody.\n")

    result = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
    )
    assert result.status is MaterializeStatus.CREATED

    body = _body_of(result.page_path)
    assert "## Sources" in body
    assert "- URL:" not in body
    hash12 = result.source_hash[:12]
    expected = (
        f"- Archive: [sources/2026/04/{hash12}-paper.pdf](sources/2026/04/{hash12}-paper.pdf)"
    )
    assert expected in body


def test_no_archive_flag_emits_url_only(tmp_path: Path) -> None:
    """--no-archive + URL → only the URL bullet, no Archive bullet."""
    raw, wiki, state_path = _vault(tmp_path)
    src = raw / "foo.md"
    src.write_text("raw bytes\n", encoding="utf-8")
    draft = _draft(tmp_path)

    result = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        source_url="https://example.com/foo",
        no_archive=True,
    )
    assert result.status is MaterializeStatus.CREATED

    body = _body_of(result.page_path)
    assert "- URL: https://example.com/foo" in body
    assert "- Archive:" not in body
