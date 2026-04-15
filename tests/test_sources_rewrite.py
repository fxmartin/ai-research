"""Tests for the ``ai-research sources rewrite`` verb (Story 08.2-001)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.state import SourceRecord, State, save_state
from ai_research.wiki.sources_rewrite import RewriteOutcome, rewrite_sources

runner = CliRunner()


def _write_page(path: Path, frontmatter_yaml: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter_yaml}---\n{body}", encoding="utf-8")


def _make_vault(tmp_path: Path) -> tuple[Path, Path]:
    """Create vault layout (wiki/, .ai-research/state.json). Returns (wiki_dir, state_file)."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    state_file = tmp_path / ".ai-research" / "state.json"
    state_file.parent.mkdir()
    return wiki_dir, state_file


def test_legacy_url_only_page_is_backfilled(tmp_path: Path) -> None:
    """A URL-only ## Sources section is upgraded with an Archive bullet."""
    wiki_dir, state_file = _make_vault(tmp_path)
    legacy_body = "# Legacy Page\n\nBody text.\n\n## Sources\n- URL: https://example.com/foo\n"
    _write_page(
        wiki_dir / "legacy.md",
        "title: Legacy Page\nsource_hash: hash-legacy\nlocked: false\n",
        legacy_body,
    )
    state = State(
        sources={
            "hash-legacy": SourceRecord(
                page="wiki/legacy.md",
                archive_path="sources/2026/04/hash-legacy-foo.md",
            ),
        },
        pages={"wiki/legacy.md": ["hash-legacy"]},
    )
    save_state(state_file, state)

    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)

    assert [r.outcome for r in results] == [RewriteOutcome.UPDATED]
    new_text = (wiki_dir / "legacy.md").read_text(encoding="utf-8")
    assert "- URL: https://example.com/foo" in new_text
    assert (
        "- Archive: [sources/2026/04/hash-legacy-foo.md]"
        "(sources/2026/04/hash-legacy-foo.md)" in new_text
    )
    # Non-sources bytes preserved.
    assert "# Legacy Page" in new_text
    assert "Body text." in new_text


def test_new_page_with_both_bullets_is_unchanged(tmp_path: Path) -> None:
    """A page already carrying URL + Archive bullets is a byte-identical no-op."""
    wiki_dir, state_file = _make_vault(tmp_path)
    body = (
        "# Already New\n\n"
        "## Sources\n"
        "- URL: https://example.com/new\n"
        "- Archive: [sources/2026/04/h2-new.md](sources/2026/04/h2-new.md)\n"
    )
    _write_page(
        wiki_dir / "already-new.md",
        "title: Already New\nsource_hash: h2\nlocked: false\n",
        body,
    )
    state = State(
        sources={
            "h2": SourceRecord(
                page="wiki/already-new.md",
                archive_path="sources/2026/04/h2-new.md",
            ),
        },
        pages={"wiki/already-new.md": ["h2"]},
    )
    save_state(state_file, state)

    before = (wiki_dir / "already-new.md").read_bytes()
    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)

    assert [r.outcome for r in results] == [RewriteOutcome.UNCHANGED]
    assert (wiki_dir / "already-new.md").read_bytes() == before


def test_pre_migration_page_preserves_url_only(tmp_path: Path) -> None:
    """A page whose source has no archive_path in state stays URL-only."""
    wiki_dir, state_file = _make_vault(tmp_path)
    body = "# Pre-migration\n\n## Sources\n- URL: https://example.com/pre\n"
    _write_page(
        wiki_dir / "pre-mig.md",
        "title: Pre-migration\nsource_hash: h-pre\nlocked: false\n",
        body,
    )
    state = State(
        sources={"h-pre": SourceRecord(page="wiki/pre-mig.md", archive_path=None)},
        pages={"wiki/pre-mig.md": ["h-pre"]},
    )
    save_state(state_file, state)

    before = (wiki_dir / "pre-mig.md").read_bytes()
    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)

    assert [r.outcome for r in results] == [RewriteOutcome.UNCHANGED]
    assert (wiki_dir / "pre-mig.md").read_bytes() == before


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """`--dry-run` reports UPDATED but leaves bytes untouched."""
    wiki_dir, state_file = _make_vault(tmp_path)
    body = "# Legacy\n\n## Sources\n- URL: https://example.com/x\n"
    _write_page(
        wiki_dir / "legacy.md",
        "title: Legacy\nsource_hash: hx\nlocked: false\n",
        body,
    )
    state = State(
        sources={"hx": SourceRecord(page="wiki/legacy.md", archive_path="sources/2026/04/hx-x.md")},
        pages={"wiki/legacy.md": ["hx"]},
    )
    save_state(state_file, state)

    before = (wiki_dir / "legacy.md").read_bytes()
    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file, dry_run=True)

    assert [r.outcome for r in results] == [RewriteOutcome.UPDATED]
    assert (wiki_dir / "legacy.md").read_bytes() == before


def test_locked_page_skipped_without_force(tmp_path: Path) -> None:
    wiki_dir, state_file = _make_vault(tmp_path)
    body = "# L\n\n## Sources\n- URL: https://example.com/l\n"
    _write_page(
        wiki_dir / "locked.md",
        "title: L\nsource_hash: hl\nlocked: true\n",
        body,
    )
    state = State(
        sources={"hl": SourceRecord(page="wiki/locked.md", archive_path="sources/2026/04/hl-l.md")},
        pages={"wiki/locked.md": ["hl"]},
    )
    save_state(state_file, state)

    before = (wiki_dir / "locked.md").read_bytes()
    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)

    assert [r.outcome for r in results] == [RewriteOutcome.LOCKED]
    assert (wiki_dir / "locked.md").read_bytes() == before


def test_locked_page_rewritten_with_force(tmp_path: Path) -> None:
    wiki_dir, state_file = _make_vault(tmp_path)
    body = "# L\n\n## Sources\n- URL: https://example.com/l\n"
    _write_page(
        wiki_dir / "locked.md",
        "title: L\nsource_hash: hl\nlocked: true\n",
        body,
    )
    state = State(
        sources={"hl": SourceRecord(page="wiki/locked.md", archive_path="sources/2026/04/hl-l.md")},
        pages={"wiki/locked.md": ["hl"]},
    )
    save_state(state_file, state)

    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file, force=True)

    assert [r.outcome for r in results] == [RewriteOutcome.UPDATED]
    text = (wiki_dir / "locked.md").read_text(encoding="utf-8")
    assert "- Archive: [sources/2026/04/hl-l.md]" in text


def test_byte_diff_outside_sources_is_zero(tmp_path: Path) -> None:
    """The rewrite touches only the bytes at/below ## Sources."""
    wiki_dir, state_file = _make_vault(tmp_path)
    above = (
        "# Rich Page\n\n"
        "Paragraph one with [[wikilink]] and more text.\n\n"
        "## Section A\n\n"
        "- item 1\n"
        "- item 2\n\n"
        "Another paragraph.\n\n"
    )
    body = above + "## Sources\n- URL: https://example.com/rich\n"
    _write_page(
        wiki_dir / "rich.md",
        "title: Rich Page\nsource_hash: hr\nlocked: false\n",
        body,
    )
    state = State(
        sources={"hr": SourceRecord(page="wiki/rich.md", archive_path="sources/2026/04/hr-r.md")},
        pages={"wiki/rich.md": ["hr"]},
    )
    save_state(state_file, state)

    rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)

    new_text = (wiki_dir / "rich.md").read_text(encoding="utf-8")
    # Split on the ## Sources heading — everything above must be byte-identical.
    above_new, _, _ = new_text.partition("## Sources")
    above_old, _, _ = (
        "---\ntitle: Rich Page\nsource_hash: hr\nlocked: false\n---\n" + body
    ).partition("## Sources")
    assert above_new == above_old


def test_cli_rewrite_integration(tmp_path: Path) -> None:
    """Invoke via Typer CLI to confirm the command wiring."""
    wiki_dir, state_file = _make_vault(tmp_path)
    body = "# Page\n\n## Sources\n- URL: https://example.com/p\n"
    _write_page(
        wiki_dir / "page.md",
        "title: Page\nsource_hash: hp\nlocked: false\n",
        body,
    )
    state = State(
        sources={"hp": SourceRecord(page="wiki/page.md", archive_path="sources/2026/04/hp-p.md")},
        pages={"wiki/page.md": ["hp"]},
    )
    save_state(state_file, state)
    index_file = tmp_path / ".ai-research" / "index.md"

    result = runner.invoke(
        app,
        [
            "sources",
            "rewrite",
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_file),
            "--index-file",
            str(index_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "UPDATED" in result.output
    assert index_file.exists()


def test_concepts_subdir_ignored(tmp_path: Path) -> None:
    """Concept stubs under wiki/concepts/ are not walked."""
    wiki_dir, state_file = _make_vault(tmp_path)
    (wiki_dir / "concepts").mkdir()
    (wiki_dir / "concepts" / "foo.md").write_text(
        "---\ntitle: Foo\nstub: true\n---\n# Foo\n\nStub.\n",
        encoding="utf-8",
    )
    save_state(state_file, State())

    results = rewrite_sources(wiki_dir=wiki_dir, state_path=state_file)
    assert results == []
