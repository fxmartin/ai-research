"""Tests for Story 02.2-002: materialize auto-triggers index-rebuild.

A successful materialize (CREATED or UPDATED) should refresh
``.ai-research/index.md``. SKIPPED/LOCKED outcomes must not. A
``skip_index=True`` opt-out is provided for bulk callers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.wiki.materialize import MaterializeStatus, materialize

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def _setup(
    tmp_path: Path, body: str = "# Attention\n\nBody.\n"
) -> tuple[Path, Path, Path, Path, Path]:
    source = tmp_path / "sources" / "paper.md"
    source.parent.mkdir(parents=True)
    source.write_text("raw\n", encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text(body, encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"
    index_path = tmp_path / ".ai-research" / "index.md"
    return source, draft, wiki_dir, state_path, index_path


def test_materialize_created_triggers_index_rebuild(tmp_path: Path) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.CREATED
    assert index_path.exists()
    content = index_path.read_text(encoding="utf-8")
    assert "attention.md" in content
    assert "title: Attention" in content


def test_materialize_updated_triggers_index_rebuild(tmp_path: Path) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    # Change source contents so hash differs -> UPDATED on re-materialize.
    source.write_text("raw v2\n", encoding="utf-8")
    draft.write_text("# Attention\n\nBody v2 with [[link]].\n", encoding="utf-8")
    index_path.unlink()  # verify it gets rebuilt

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.UPDATED
    assert index_path.exists()


def test_materialize_skipped_does_not_rebuild_index(tmp_path: Path) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )
    # Delete the index; a SKIPPED run must NOT recreate it.
    index_path.unlink()

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.SKIPPED
    assert not index_path.exists()


def test_materialize_locked_does_not_rebuild_index(tmp_path: Path) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    # Flip the page's frontmatter to locked.
    page = wiki_dir / "attention.md"
    text = page.read_text(encoding="utf-8")
    page.write_text(text.replace("locked: false", "locked: true"), encoding="utf-8")

    # Change source so we'd otherwise UPDATE.
    source.write_text("raw v2\n", encoding="utf-8")
    index_path.unlink()

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.LOCKED
    assert not index_path.exists()


def test_materialize_skip_index_opt_out(tmp_path: Path) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        index_path=index_path,
        skip_index=True,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.CREATED
    assert not index_path.exists()


def test_materialize_no_index_path_leaves_index_alone(tmp_path: Path) -> None:
    """When index_path is None, behavior is backwards-compatible (no rebuild)."""
    source, draft, wiki_dir, state_path, _ = _setup(tmp_path)

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert result.status is MaterializeStatus.CREATED
    # No index file should appear — nothing told materialize where to put one.
    assert not (tmp_path / ".ai-research" / "index.md").exists()


# ---- CLI ------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_materialize_rebuilds_index_by_default(tmp_path: Path, runner: CliRunner) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--from",
            str(draft),
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_path),
            "--index-file",
            str(index_path),
        ],
    )

    assert res.exit_code == 0, res.output
    assert index_path.exists()


def test_cli_materialize_skip_index_flag(tmp_path: Path, runner: CliRunner) -> None:
    source, draft, wiki_dir, state_path, index_path = _setup(tmp_path)

    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--from",
            str(draft),
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_path),
            "--index-file",
            str(index_path),
            "--skip-index",
        ],
    )

    assert res.exit_code == 0, res.output
    assert not index_path.exists()
