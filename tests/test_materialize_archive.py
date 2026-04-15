"""Archive-after-materialize tests (Story 07.1-002).

Verifies that ``materialize`` moves the source file into
``sources/<yyyy>/<mm>/<hash12>-<slug>.<ext>`` on CREATED / UPDATED / SKIPPED,
skips the move on LOCKED or error, and rolls back state on archive failure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter
import pytest

from ai_research.archive import ArchiveHashCollisionError, compute_archive_path
from ai_research.state import load_state
from ai_research.wiki.materialize import MaterializeStatus, materialize

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)
LATER_NOW = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)


def _vault(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Set up a repo-shaped workspace. Returns (raw, wiki, state, sources)."""
    wiki = tmp_path / "wiki"
    raw = wiki / "raw"
    raw.mkdir(parents=True)
    sources = tmp_path / "sources"
    state = tmp_path / ".ai-research" / "state.json"
    return raw, wiki, state, sources


def _write_source(raw: Path, name: str = "foo.md", content: str = "raw bytes\n") -> Path:
    src = raw / name
    src.write_text(content, encoding="utf-8")
    return src


def _draft(tmp_path: Path, body: str = "# Foo\n\nBody.\n") -> Path:
    d = tmp_path / "draft.md"
    d.write_text(body, encoding="utf-8")
    return d


def test_created_archives_source(tmp_path: Path) -> None:
    """After a CREATED materialize, source is gone from raw/ and present in sources/."""
    raw, wiki, state_path, sources = _vault(tmp_path)
    src = _write_source(raw)
    draft = _draft(tmp_path)

    result = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.CREATED
    assert not src.exists(), "source should have been moved out of raw/"

    state = load_state(state_path)
    record = state.sources[result.source_hash]
    assert record.archive_path is not None
    archived = tmp_path / record.archive_path
    assert archived.exists(), f"expected archived file at {archived}"
    assert archived.read_text(encoding="utf-8") == "raw bytes\n"
    # Layout check: sources/<yyyy>/<mm>/<hash12>-<slug>.md
    assert archived.parent == sources / "2026" / "04"
    assert archived.name.endswith("-foo.md")
    assert archived.name.startswith(result.source_hash[:12])


def test_source_outside_raw_still_archives(tmp_path: Path) -> None:
    """A source at an arbitrary path is still archived into sources/."""
    _, wiki, state_path, sources = _vault(tmp_path)
    external = tmp_path / "scratch" / "paper.md"
    external.parent.mkdir(parents=True)
    external.write_text("external\n", encoding="utf-8")
    draft = _draft(tmp_path, "# External\n\nBody.\n")

    result = materialize(
        source=external,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.CREATED
    assert not external.exists()
    state = load_state(state_path)
    assert state.sources[result.source_hash].archive_path is not None


def test_no_archive_flag_preserves_source(tmp_path: Path) -> None:
    """--no-archive leaves the source in place and records archive_path=None."""
    raw, wiki, state_path, _sources = _vault(tmp_path)
    src = _write_source(raw)
    draft = _draft(tmp_path)

    result = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        no_archive=True,
    )

    assert result.status is MaterializeStatus.CREATED
    assert src.exists(), "source should still be at original path"
    state = load_state(state_path)
    assert state.sources[result.source_hash].archive_path is None


def test_locked_page_does_not_archive(tmp_path: Path) -> None:
    """LOCKED short-circuit must not move the source."""
    raw, wiki, state_path, sources = _vault(tmp_path)
    src = _write_source(raw)
    draft = _draft(tmp_path)

    # First run (no-archive so we can reuse the source) to create the page.
    r1 = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        no_archive=True,
    )
    assert r1.status is MaterializeStatus.CREATED
    post = frontmatter.loads(r1.page_path.read_text(encoding="utf-8"))
    post["locked"] = True
    r1.page_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    # Change the source so hash differs, then re-materialize WITH archiving on.
    src.write_text("v2 bytes\n", encoding="utf-8")

    r2 = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.LOCKED
    assert src.exists(), "LOCKED must leave the source in raw/ for retry"
    assert not (sources / "2026" / "04").exists() or not any((sources / "2026" / "04").iterdir()), (
        "LOCKED must never archive"
    )


def test_skipped_still_archives_idempotently(tmp_path: Path) -> None:
    """SKIPPED: page unchanged, but a still-in-raw source gets archived."""
    raw, wiki, state_path, sources = _vault(tmp_path)
    src = _write_source(raw)
    draft = _draft(tmp_path)

    # First pass with --no-archive to create the page but leave source behind.
    r1 = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        no_archive=True,
    )
    assert r1.status is MaterializeStatus.CREATED
    assert src.exists()

    # Second pass same hash → SKIPPED. With archiving on the source moves now.
    r2 = materialize(
        source=src,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.SKIPPED
    assert not src.exists()
    state = load_state(state_path)
    assert state.sources[r2.source_hash].archive_path is not None


def test_archive_collision_preserves_page_and_rolls_back_state(tmp_path: Path) -> None:
    """ArchiveHashCollisionError: page is preserved, state has no bogus path."""
    raw, wiki, state_path, sources = _vault(tmp_path)
    src = _write_source(raw, content="real bytes\n")
    draft = _draft(tmp_path)

    # Pre-plant a collision: a different file at the canonical target path.
    target = compute_archive_path(source=src, sources_root=sources, title="Foo", now=FIXED_NOW)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"tampered bytes\n")

    with pytest.raises(ArchiveHashCollisionError):
        materialize(
            source=src,
            draft_path=draft,
            wiki_dir=wiki,
            state_path=state_path,
            now=FIXED_NOW,
        )

    # Page IS written (atomic_write happens before archive).
    page = wiki / "foo.md"
    assert page.exists(), "page write should be preserved on archive failure"
    # Source stays for manual review.
    assert src.exists()
    # State is not polluted: either absent (no save_state ran) or has no
    # archive_path pointing at the conflicting target.
    if state_path.exists():
        state = load_state(state_path)
        for rec in state.sources.values():
            assert rec.archive_path is None or not rec.archive_path.endswith(target.name)
