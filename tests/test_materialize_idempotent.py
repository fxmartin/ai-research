"""Tests for idempotent re-ingest via source_hash (Story 02.1-002)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from ai_research.state import load_state
from ai_research.wiki.materialize import (
    MaterializeStatus,
    materialize,
)

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)
LATER_NOW = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)


def _setup(tmp_path: Path, content: str = "raw bytes\n") -> Path:
    src = tmp_path / "sources" / "paper.md"
    src.parent.mkdir(parents=True)
    src.write_text(content, encoding="utf-8")
    return src


def _draft(tmp_path: Path, body: str = "# Title\n\nBody.\n") -> Path:
    draft = tmp_path / "draft.md"
    draft.write_text(body, encoding="utf-8")
    return draft


def test_unchanged_source_hash_is_noop(tmp_path: Path) -> None:
    """Same hash, same page: file mtime unchanged, status is SKIPPED."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    assert r1.status is MaterializeStatus.CREATED
    mtime_before = r1.page_path.stat().st_mtime_ns

    # Sleep to ensure mtime would change if we rewrote.
    time.sleep(0.02)

    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.SKIPPED
    assert r2.page_path == r1.page_path
    assert r2.page_path.stat().st_mtime_ns == mtime_before

    # Frontmatter ingested_at should not have been refreshed.
    post = frontmatter.loads(r2.page_path.read_text(encoding="utf-8"))
    assert post["ingested_at"] == FIXED_NOW.isoformat()


def test_locked_page_is_not_overwritten(tmp_path: Path) -> None:
    """locked: true with a different hash: skip write, status LOCKED."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    # Flip lock on.
    post = frontmatter.loads(r1.page_path.read_text(encoding="utf-8"))
    post["locked"] = True
    r1.page_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    mtime_before = r1.page_path.stat().st_mtime_ns
    body_before = r1.page_path.read_text(encoding="utf-8")

    # Change the source so hash differs.
    source.write_text("different bytes now\n", encoding="utf-8")
    time.sleep(0.02)

    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.LOCKED
    assert r2.page_path.stat().st_mtime_ns == mtime_before
    assert r2.page_path.read_text(encoding="utf-8") == body_before


def test_changed_source_hash_updates_page(tmp_path: Path) -> None:
    """New hash for same source: body + ingested_at + source_hash refresh."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path, "# Title\n\nOriginal body.\n")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    old_hash = r1.source_hash

    # New source contents → new hash. New draft body too.
    source.write_text("v2 bytes\n", encoding="utf-8")
    draft.write_text("# Title\n\nUpdated body.\n", encoding="utf-8")

    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.UPDATED
    assert r2.source_hash != old_hash
    assert r2.page_path == r1.page_path

    post = frontmatter.loads(r2.page_path.read_text(encoding="utf-8"))
    assert post["source_hash"] == r2.source_hash
    assert post["ingested_at"] == LATER_NOW.isoformat()
    assert post["locked"] is False
    assert "Updated body." in post.content

    # State retains both historical hashes in pages[] but maps sources[new]=page.
    state = load_state(state_path)
    rel = str(r2.page_path.relative_to(tmp_path))
    assert state.sources[r2.source_hash] == rel
    assert old_hash in state.pages[rel]
    assert r2.source_hash in state.pages[rel]


def test_force_bypasses_lock(tmp_path: Path) -> None:
    """--force overwrites even when locked: true."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    post = frontmatter.loads(r1.page_path.read_text(encoding="utf-8"))
    post["locked"] = True
    r1.page_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    source.write_text("v2 bytes\n", encoding="utf-8")
    draft.write_text("# Title\n\nForced body.\n", encoding="utf-8")

    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
        force=True,
    )
    assert r2.status is MaterializeStatus.UPDATED
    post_after = frontmatter.loads(r2.page_path.read_text(encoding="utf-8"))
    assert "Forced body." in post_after.content
    # Force preserves the lock flag so the page stays protected thereafter.
    assert post_after["locked"] is True


def test_force_on_unchanged_hash_still_rewrites(tmp_path: Path) -> None:
    """--force rewrites even when the hash is unchanged."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
        force=True,
    )
    assert r2.status is MaterializeStatus.UPDATED
    post = frontmatter.loads(r2.page_path.read_text(encoding="utf-8"))
    assert post["ingested_at"] == LATER_NOW.isoformat()


def test_cli_emits_status_and_exits_zero_on_skip(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    args = [
        "materialize",
        "--source",
        str(source),
        "--from",
        str(draft),
        "--wiki-dir",
        str(wiki_dir),
        "--state-file",
        str(state_path),
    ]
    r1 = runner.invoke(app, args)
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(app, args)
    assert r2.exit_code == 0, r2.output
    assert "skipped" in r2.output.lower()


def test_cli_warns_and_exits_zero_when_locked(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    args = [
        "materialize",
        "--source",
        str(source),
        "--from",
        str(draft),
        "--wiki-dir",
        str(wiki_dir),
        "--state-file",
        str(state_path),
    ]
    r1 = runner.invoke(app, args)
    assert r1.exit_code == 0, r1.output

    page_path = wiki_dir / "title.md"
    post = frontmatter.loads(page_path.read_text(encoding="utf-8"))
    post["locked"] = True
    page_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    source.write_text("v2\n", encoding="utf-8")

    r2 = runner.invoke(app, args)
    assert r2.exit_code == 0, r2.output
    assert "lock" in r2.output.lower()


def test_cli_force_flag(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    base = [
        "materialize",
        "--source",
        str(source),
        "--from",
        str(draft),
        "--wiki-dir",
        str(wiki_dir),
        "--state-file",
        str(state_path),
    ]
    r1 = runner.invoke(app, base)
    assert r1.exit_code == 0, r1.output

    page_path = wiki_dir / "title.md"
    post = frontmatter.loads(page_path.read_text(encoding="utf-8"))
    post["locked"] = True
    page_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    source.write_text("v2\n", encoding="utf-8")
    draft.write_text("# Title\n\nForced.\n", encoding="utf-8")

    r2 = runner.invoke(app, [*base, "--force"])
    assert r2.exit_code == 0, r2.output
    assert "Forced." in page_path.read_text(encoding="utf-8")


def test_page_recorded_in_state_but_missing_on_disk_recreates(tmp_path: Path) -> None:
    """If state knows the hash but the page file is gone, recreate it."""
    source = _setup(tmp_path)
    draft = _draft(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    r1.page_path.unlink()

    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=LATER_NOW,
    )
    assert r2.status is MaterializeStatus.CREATED
    assert r2.page_path.exists()
